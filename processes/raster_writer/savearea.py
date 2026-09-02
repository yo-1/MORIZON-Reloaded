# MORIZON Reloaded - forest zoning support plugin for QGIS
# Original MORIZON implementation: Copyright (C) 2021 MIERUNE Inc.
# Modifications for QGIS 3.44: Copyright (C) 2026 Yoichi Wada
# Licensed under the GNU General Public License version 3.
# SPDX-License-Identifier: GPL-3.0-only

import os

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature, QgsFeatureRequest, QgsField, QgsFields, QgsGeometry,
    QgsCoordinateReferenceSystem, QgsProcessingException, QgsRasterLayer, QgsSpatialIndex,
    QgsVectorLayer, QgsWkbTypes
)
import processing
from osgeo import gdal
import numpy as np

from ...utils import get_tiff_info
from ...constants import OUTPUT_SAVEAREA


# 林野庁 QGIS 3.16版 MORIZON の savearea.py を基準にした QGIS 3.44 安定版。
# 原版仕様:
#   1) r.watershed threshold=500 で basin を作成
#   2) basin を polygonize -> fix geometries
#   3) 建物との重複面積 > 0 の basin を抽出
#   4) basin外=NoData, basin内で建物なし=0, 建物あり=1
# QGIS 3.44対応:
#   - grass7:r.watershed / grass:r.watershed の両IDに対応
#   - qgis:calculatevectoroverlaps と QgsRasterCalculator を使用せず、
#     PyQGISの厳密な交差面積判定 + GDAL/NumPyで出力する。
#   - 最終GeoTIFFは解析DEMのグリッド（CRS/Extent/GeoTransform/Width/Height）を継承。

NODATA_VALUE = -9999.0


def _run_watershed(basis_dem_filepath: str):
    """QGIS 3.44のGRASS provider差を吸収しつつ、原版threshold=500を維持する。"""
    common = {
        'elevation': basis_dem_filepath,
        '-4': False,
        '-a': False,
        '-b': False,
        '-m': False,
        '-s': False,
        'GRASS_RASTER_FORMAT_META': '',
        'GRASS_RASTER_FORMAT_OPT': '',
        'GRASS_REGION_CELLSIZE_PARAMETER': 0,
        'GRASS_REGION_PARAMETER': None,
        'accumulation': None,
        'basin': 'TEMPORARY_OUTPUT',
        'blocking': None,
        'convergence': 5,
        'depression': None,
        'disturbed_land': None,
        'drainage': None,
        'flow': None,
        'half_basin': None,
        'length_slope': None,
        'max_slope_length': None,
        'memory': 300,
        'slope_steepness': None,
        'spi': None,
        'stream': None,
        'tci': None,
        'threshold': 500,
    }
    errors = []
    for alg_id in ('grass:r.watershed', 'grass7:r.watershed'):
        try:
            return processing.run(alg_id, common)['basin']
        except Exception as e:
            errors.append(f'{alg_id}: {e}')
    raise QgsProcessingException(
        'r.watershed を実行できませんでした。GRASS Processing Providerを確認してください。\n'
        + '\n'.join(errors)
    )


def create_basin_polygon(basis_dem_filepath):
    """原版と同じく r.watershed(threshold=500) -> polygonize -> fixgeometries。"""
    basin_filepath = _run_watershed(basis_dem_filepath)
    vectorized_basin = processing.run('gdal:polygonize', {
        'INPUT': basin_filepath,
        'BAND': 1,
        'FIELD': 'DN',
        'EIGHT_CONNECTEDNESS': False,
        'EXTRA': '',
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })['OUTPUT']
    return processing.run('native:fixgeometries', {
        'INPUT': vectorized_basin,
        'METHOD': 1,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })['OUTPUT']


def _as_vector_layer(source):
    if isinstance(source, QgsVectorLayer):
        return source
    layer = QgsVectorLayer(str(source), 'building', 'ogr')
    if not layer.isValid():
        raise QgsProcessingException(f'建物ポリゴンを開けません: {source}')
    return layer


def _layer_crs_text(layer):
    crs = layer.crs()
    if not crs.isValid():
        return 'INVALID'
    authid = crs.authid() or '(no authid)'
    desc = crs.description() or ''
    return f'{authid} {desc}'.strip()


def _extent_text(layer):
    e = layer.extent()
    return f'{e.xMinimum():.6f},{e.xMaximum():.6f},{e.yMinimum():.6f},{e.yMaximum():.6f}'


def _append_debug(debug_log_path, lines):
    if not debug_log_path:
        return
    try:
        os.makedirs(os.path.dirname(debug_log_path), exist_ok=True)
        with open(debug_log_path, 'a', encoding='utf-8') as f:
            for line in lines:
                f.write(str(line) + '\n')
    except Exception:
        # デバッグログの失敗で本処理を止めない。
        pass


def _select_basins_with_buildings(basin_layer, building_filepath, debug_log_path=None, building_crs_override_authid=None):
    """旧MORIZONの ``calculatevectoroverlaps -> area > 0`` を再現する。

    QGIS 3.44 では入力レイヤ同士のCRSが異なる場合に暗黙の座標変換へ
    依存しないよう、保全対象レイヤを流域ポリゴンのCRSへ明示的に再投影してから
    Calculate vector overlaps を実行する。

    旧MORIZONと同様、流域ごとの保全対象との重複面積を求め、面積 > 0 の
    流域のみを抽出する。処理診断用にCRS、Extent、Feature count、追加面積
    フィールド、選択件数をログへ記録する。
    """
    basin_layer = _as_vector_layer(basin_layer)
    building_layer = _as_vector_layer(building_filepath)

    # CRS情報が欠落している場合のみ、GUI側でユーザーが明示的に選択した
    # 元CRSを処理内のレイヤへ付与する。元Shape/.prjは書き換えない。
    source_crs_before = _layer_crs_text(building_layer)
    crs_override_applied = False
    override_crs = None
    if not building_layer.crs().isValid():
        if not building_crs_override_authid:
            raise QgsProcessingException(
                '保全対象データのCRSが不明です。\n'
                '要素計算画面で「基盤地図情報（EPSG:6668）」または「CRSを指定」を選択してください。'
            )
        override_crs = QgsCoordinateReferenceSystem(str(building_crs_override_authid))
        # AUTHIDを持たないカスタムCRS等ではWKTが渡される場合も許容する。
        if not override_crs.isValid():
            override_crs = QgsCoordinateReferenceSystem()
            try:
                override_crs.createFromWkt(str(building_crs_override_authid))
            except Exception:
                pass
        if not override_crs.isValid():
            raise QgsProcessingException(
                f'指定された保全対象データの座標参照系を読み込めませんでした: {building_crs_override_authid}'
            )
        building_layer.setCrs(override_crs)
        crs_override_applied = True
        if not building_layer.crs().isValid():
            raise QgsProcessingException(
                f'保全対象データへのCRS付与に失敗しました: {building_crs_override_authid}'
            )

    _append_debug(debug_log_path, [
        '=== STEP7 SAVEAREA OVERLAP DEBUG ===',
        f'Basin CRS: {_layer_crs_text(basin_layer)}',
        f'Building CRS (original): {source_crs_before}',
        f'CRS override requested: {building_crs_override_authid}',
        f'Building CRS (assigned): {_layer_crs_text(building_layer)}',
        f'Building CRS override applied: {crs_override_applied}',
        f'Basin extent: {_extent_text(basin_layer)}',
        f'Building extent (source): {_extent_text(building_layer)}',
        f'Basin feature count: {basin_layer.featureCount()}',
        f'Building feature count (source): {building_layer.featureCount()}',
    ])

    # 旧版と同様、保全対象側の壊れたジオメトリを修復する。
    fixed_building_source = processing.run('native:fixgeometries', {
        'INPUT': building_layer,
        'METHOD': 1,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })['OUTPUT']
    fixed_building = _as_vector_layer(fixed_building_source)
    # fixgeometries の一時出力でCRSメタデータが失われた場合にも、
    # 明示的に選択された元CRSを再付与する。座標値は変更しない。
    if not fixed_building.crs().isValid() and override_crs is not None and override_crs.isValid():
        fixed_building.setCrs(override_crs)

    if not fixed_building.crs().isValid():
        _append_debug(debug_log_path, [
            'ERROR: Building CRS is still INVALID after CRS assignment/fixgeometries.',
            '=== END STEP7 DEBUG ===',
        ])
        raise QgsProcessingException(
            '保全対象データのCRS設定後もCRSがINVALIDです。重複判定は実行しません。\n'
            '診断ログ: ' + (debug_log_path or '(なし)')
        )

    basin_crs = basin_layer.crs()
    building_crs = fixed_building.crs()

    # QGIS画面上ではオンザフライ表示により重なって見えても、Processingの
    # ベクトル演算では入力座標を明示的に同一CRSへそろえる方が安全である。
    if basin_crs.isValid() and building_crs.isValid() and basin_crs != building_crs:
        reprojected_source = processing.run('native:reprojectlayer', {
            'INPUT': fixed_building,
            'TARGET_CRS': basin_crs,
            'CONVERT_CURVED_GEOMETRIES': False,
            'OPERATION': '',
            'OUTPUT': 'TEMPORARY_OUTPUT'
        })['OUTPUT']
        fixed_building = _as_vector_layer(reprojected_source)
        _append_debug(debug_log_path, [
            'CRS action: building layer explicitly reprojected to basin CRS.',
            f'Building CRS (working): {_layer_crs_text(fixed_building)}',
            f'Building extent (working): {_extent_text(fixed_building)}',
        ])
    elif basin_crs.isValid() and building_crs.isValid():
        _append_debug(debug_log_path, [
            'CRS action: no reprojection required (same CRS).',
            f'Building CRS (working): {_layer_crs_text(fixed_building)}',
            f'Building extent (working): {_extent_text(fixed_building)}',
        ])
    else:
        _append_debug(debug_log_path, [
            'ERROR: Basin or building CRS is invalid before overlap.',
            f'Building CRS (working): {_layer_crs_text(fixed_building)}',
            '=== END STEP7 DEBUG ===',
        ])
        raise QgsProcessingException(
            '流域または保全対象データのCRSがINVALIDです。重複判定は実行しません。\n'
            '診断ログ: ' + (debug_log_path or '(なし)')
        )

    # overlap直前の安全確認。CRSだけでなく、再投影後のextentも記録する。
    if not basin_layer.crs().isValid() or not fixed_building.crs().isValid():
        raise QgsProcessingException('重複判定直前のCRS検証に失敗しました。')
    _append_debug(debug_log_path, [
        f'Pre-overlap Basin CRS: {_layer_crs_text(basin_layer)}',
        f'Pre-overlap Building CRS: {_layer_crs_text(fixed_building)}',
        f'Pre-overlap Basin extent: {_extent_text(basin_layer)}',
        f'Pre-overlap Building extent: {_extent_text(fixed_building)}',
    ])

    # 旧版 qgis:calculatevectoroverlaps と同等の Processing を使う。
    # QGIS 3.44系では native:calculatevectoroverlaps が標準。
    overlap_source = None
    used_alg_id = None
    errors = []
    for alg_id in ('native:calculatevectoroverlaps', 'qgis:calculatevectoroverlaps'):
        try:
            overlap_source = processing.run(alg_id, {
                'INPUT': basin_layer,
                'LAYERS': [fixed_building],
                'OUTPUT': 'TEMPORARY_OUTPUT'
            })['OUTPUT']
            used_alg_id = alg_id
            break
        except Exception as e:
            errors.append(f'{alg_id}: {e}')

    if overlap_source is None:
        _append_debug(debug_log_path, ['Calculate vector overlaps errors:'] + errors)
        raise QgsProcessingException(
            'Calculate vector overlaps を実行できませんでした。\n' + '\n'.join(errors)
        )

    overlap_layer = _as_vector_layer(overlap_source)

    # Calculate vector overlaps が追加した面積フィールドを特定する。
    basin_field_names = {f.name() for f in basin_layer.fields()}
    added_fields = [f.name() for f in overlap_layer.fields()
                    if f.name() not in basin_field_names]
    area_fields = [n for n in added_fields if n.lower().endswith('_area')]
    if not area_fields:
        area_fields = [f.name() for f in overlap_layer.fields()
                       if f.name().lower().endswith('_area')]

    _append_debug(debug_log_path, [
        f'Overlap algorithm: {used_alg_id}',
        f'Overlap output feature count: {overlap_layer.featureCount()}',
        f'Added fields: {added_fields}',
        f'Overlap area fields: {area_fields}',
    ])

    if not area_fields:
        raise QgsProcessingException(
            'Calculate vector overlaps の出力に重複面積フィールド（*_area）がありません。'
        )

    # 面積フィールドの実値も診断する。旧版の判定条件は strictly > 0。
    positive_feature_count = 0
    max_overlap_area = 0.0
    sum_overlap_area = 0.0
    for feat in overlap_layer.getFeatures():
        positive = False
        for name in area_fields:
            value = feat[name]
            try:
                area = float(value) if value is not None else 0.0
            except (TypeError, ValueError):
                area = 0.0
            if np.isfinite(area):
                max_overlap_area = max(max_overlap_area, area)
                sum_overlap_area += max(area, 0.0)
                if area > 0.0:
                    positive = True
        if positive:
            positive_feature_count += 1

    expression = ' OR '.join(
        f'coalesce("{name}", 0) > 0' for name in area_fields
    )
    selected_source = processing.run('native:extractbyexpression', {
        'INPUT': overlap_layer,
        'EXPRESSION': expression,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })['OUTPUT']
    selected_layer = _as_vector_layer(selected_source)

    _append_debug(debug_log_path, [
        f'Overlap positive feature count (direct scan): {positive_feature_count}',
        f'Max overlap area: {max_overlap_area}',
        f'Sum overlap area: {sum_overlap_area}',
        f'Extract expression: {expression}',
        f'Selected basin count: {selected_layer.featureCount()}',
        '=== END STEP7 DEBUG ===',
    ])

    if fixed_building.featureCount() > 0 and basin_layer.featureCount() > 0 \
            and selected_layer.featureCount() == 0:
        raise QgsProcessingException(
            '保全対象と重複する流域が0件でした。\n'
            f'流域CRS: {_layer_crs_text(basin_layer)}\n'
            f'保全対象CRS: {_layer_crs_text(fixed_building)}\n'
            f'最大重複面積: {max_overlap_area}\n'
            '診断ログ: ' + (debug_log_path or '(なし)')
        )

    return selected_layer

def _rasterize_to_reference(vector_layer, reference_dem, output_path):
    """参照DEMと完全一致するグリッドへ1を焼き込む。"""
    ds = gdal.Open(reference_dem, gdal.GA_ReadOnly)
    if ds is None:
        raise QgsProcessingException(f'DEMを開けません: {reference_dem}')
    gt = ds.GetGeoTransform()
    xsize, ysize = ds.RasterXSize, ds.RasterYSize
    xmin = gt[0]
    ymax = gt[3]
    xmax = xmin + gt[1] * xsize + gt[2] * ysize
    ymin = ymax + gt[4] * xsize + gt[5] * ysize
    ds = None

    return processing.run('gdal:rasterize', {
        'INPUT': vector_layer,
        'FIELD': None,
        'BURN': 1,
        'USE_Z': False,
        'UNITS': 1,
        'WIDTH': abs(gt[1]),
        'HEIGHT': abs(gt[5]),
        'EXTENT': f'{min(xmin,xmax)},{max(xmin,xmax)},{min(ymin,ymax)},{max(ymin,ymax)}',
        'NODATA': 0,
        'OPTIONS': 'COMPRESS=LZW',
        'DATA_TYPE': 0,  # Byte
        'INIT': 0,
        'INVERT': False,
        'EXTRA': '',
        'OUTPUT': output_path
    })['OUTPUT']


def _write_final(reference_dem, basin_mask_path, selected_mask_path, output_path):
    ref = gdal.Open(reference_dem, gdal.GA_ReadOnly)
    basin_ds = gdal.Open(basin_mask_path, gdal.GA_ReadOnly)
    sel_ds = gdal.Open(selected_mask_path, gdal.GA_ReadOnly)
    if ref is None or basin_ds is None or sel_ds is None:
        raise QgsProcessingException('STEP7中間ラスタを開けません。')

    dem_band = ref.GetRasterBand(1)
    dem = dem_band.ReadAsArray()
    dem_nd = dem_band.GetNoDataValue()
    basin = basin_ds.GetRasterBand(1).ReadAsArray()
    selected = sel_ds.GetRasterBand(1).ReadAsArray()

    valid_dem = np.isfinite(dem)
    if dem_nd is not None:
        valid_dem &= ~np.isclose(dem, dem_nd)
    # 原版: basinポリゴンなし=NoData, basinあり建物なし=0, 建物あり=1
    out = np.full(dem.shape, NODATA_VALUE, dtype=np.float32)
    basin_present = (basin == 1) & valid_dem
    out[basin_present] = 0.0
    out[(selected == 1) & basin_present] = 1.0

    driver = gdal.GetDriverByName('GTiff')
    dst = driver.Create(
        output_path, ref.RasterXSize, ref.RasterYSize, 1, gdal.GDT_Float32,
        options=['COMPRESS=LZW', 'TILED=YES', 'BIGTIFF=IF_SAFER']
    )
    if dst is None:
        raise QgsProcessingException(f'出力を作成できません: {output_path}')
    dst.SetGeoTransform(ref.GetGeoTransform())
    dst.SetProjection(ref.GetProjection())
    band = dst.GetRasterBand(1)
    band.SetNoDataValue(NODATA_VALUE)
    band.WriteArray(out)
    band.FlushCache()
    dst.FlushCache()
    dst = None
    ref = basin_ds = sel_ds = None
    return output_path


def generate(basis_dem_filepath: str, building_filepath: str, output_dir: str, building_crs_override_authid=None) -> str:
    """保全対象を含む流域ラスターを生成（林野庁原版照合済みSTEP7B）。"""
    os.makedirs(output_dir, exist_ok=True)
    work_dir = os.path.join(output_dir, '_MORIZON_work')
    os.makedirs(work_dir, exist_ok=True)
    debug_log = os.path.join(work_dir, 'step7_savearea_debug.txt')
    try:
        if os.path.exists(debug_log):
            os.remove(debug_log)
    except OSError:
        pass

    basin_layer = create_basin_polygon(basis_dem_filepath)
    selected_layer = _select_basins_with_buildings(
        basin_layer, building_filepath, debug_log, building_crs_override_authid
    )

    basin_mask = os.path.join(work_dir, 'step7b_basin_mask.tif')
    selected_mask = os.path.join(work_dir, 'step7b_selected_mask.tif')

    # 既存中間ファイルは、QGISレイヤとして開いていないので安全に更新できる。
    for p in (basin_mask, selected_mask):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass

    _rasterize_to_reference(basin_layer, basis_dem_filepath, basin_mask)
    _rasterize_to_reference(selected_layer, basis_dem_filepath, selected_mask)

    output_filepath = os.path.join(
        output_dir, OUTPUT_SAVEAREA['FILE_NAME'] + '.tif'
    )

    # STEP7B5:
    # 最終ファイルを直接作らず、必ず一時GeoTIFFへ完全に書き出して
    # GDALハンドルを閉じてから公開する。これにより「出力中の自己ロック」を避ける。
    import uuid
    temp_final = os.path.join(
        work_dir, f"step7b_final_{uuid.uuid4().hex}.tif"
    )
    _write_final(
        basis_dem_filepath, basin_mask, selected_mask, temp_final
    )

    def _next_versioned_path(path):
        stem, ext = os.path.splitext(path)
        i = 2
        while os.path.exists(f"{stem}_v{i}{ext}"):
            i += 1
        return f"{stem}_v{i}{ext}"

    target = output_filepath

    # まず標準名へ公開を試みる。
    if os.path.exists(target):
        try:
            os.remove(target)
        except PermissionError:
            # QGIS/GDAL/Windowsが旧結果を保持している場合は、
            # 旧ファイルを壊さず新世代へ出力する。
            target = _next_versioned_path(output_filepath)
        except OSError:
            target = _next_versioned_path(output_filepath)

    try:
        # 同一ドライブ内なので原子的なrenameとなる。
        os.replace(temp_final, target)
    except PermissionError:
        # 競合が発生した場合もさらに別世代へ退避。
        target = _next_versioned_path(output_filepath)
        os.replace(temp_final, target)
    finally:
        try:
            if os.path.exists(temp_final):
                os.remove(temp_final)
        except OSError:
            pass

    return target


def dissolve_basin_vlayer(basin_vlayer_filepath):
    """流域ポリゴンをDNフィールドでdissolveする（原版互換）。"""
    return processing.run('native:dissolve', {
        'FIELD': ['DN'],
        'INPUT': basin_vlayer_filepath,
        'OUTPUT': 'TEMPORARY_OUTPUT'
    })['OUTPUT']
