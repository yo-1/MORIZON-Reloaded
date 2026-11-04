import json, pathlib, hashlib
import numpy as np
from osgeo import gdal
from qgis.core import QgsRasterLayer

root = pathlib.Path('C:/Users/Yoichi_Wada/Documents/Github/MORIZON-Reloaded/.validation/pr19-evidence')
rows = []
for p in sorted((root/'ZoningKit/YOUSO').glob('*.tif')):
    ds = gdal.Open(str(p))
    row = {'name': p.name, 'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'gdal_valid': ds is not None}
    layer = QgsRasterLayer(str(p), p.stem)
    row.update(qgis_valid=layer.isValid(), crs=layer.crs().authid())
    if ds:
        band = ds.GetRasterBand(1)
        a = band.ReadAsArray()
        nd = band.GetNoDataValue()
        mask = np.ones(a.shape, dtype=bool) if nd is None else (a != nd)
        if nd is not None and np.isnan(nd):
            mask = ~np.isnan(a)
        valid = a[mask]
        finite = valid[np.isfinite(valid)]
        row.update(size=[ds.RasterXSize,ds.RasterYSize], geotransform=ds.GetGeoTransform(), nodata=nd, datatype=gdal.GetDataTypeName(band.DataType), valid_pixels=int(mask.sum()), nodata_pixels=int((~mask).sum()), nonfinite_valid_pixels=int((~np.isfinite(valid)).sum()), minimum=float(finite.min()) if finite.size else None, maximum=float(finite.max()) if finite.size else None)
        if p.name in ['Y_02_shuzai.tif','Y_13_hozen.tif']:
            values,counts=np.unique(finite,return_counts=True)
            row['category_counts']={str(v):int(n) for v,n in zip(values,counts)}
        ds=None
    rows.append(row)
result={'rasters':rows,'count':len(rows),'same_grid':bool(rows) and all(r.get('geotransform')==rows[0].get('geotransform') and r.get('size')==rows[0].get('size') and r.get('crs')==rows[0].get('crs') for r in rows),'all_readable_and_nonempty':bool(rows) and all(r['qgis_valid'] and r['gdal_valid'] and r.get('valid_pixels',0)>0 and r.get('nonfinite_valid_pixels')==0 for r in rows)}
(root/'output-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
