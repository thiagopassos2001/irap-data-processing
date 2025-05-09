import geopandas as gpd
import pandas as pd
import exifread
import zipfile
import shapely
import shutil
import numpy as np
import os
from until import *

import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

def GetExifMetadata(img_path):
    """
    Extrai os metadados do arquivo
    """
    with open(img_path, 'rb') as f:
        metadata_dict = exifread.process_file(f)
    
    return metadata_dict

def ConvertMetadataCoordToDegrees(value,ref):
    d = float(value[0].num) / float(value[0].den)
    m = float(value[1].num) / float(value[1].den)
    s = float(value[2].num) / float(value[2].den)

    coord = d + (m / 60.0) + (s / 3600.0)

    if ref in ["S","W"]:
        coord = -coord

    return coord

def GetCoord(metadata_dict):
    """
    Extrai as coordenadas dos arquivos
    """
    if not metadata_dict:
        return None
    
    gps_latitude = metadata_dict.get('GPS GPSLatitude')
    gps_latitude_ref = metadata_dict.get('GPS GPSLatitudeRef')
    gps_longitude = metadata_dict.get('GPS GPSLongitude')
    gps_longitude_ref = metadata_dict.get('GPS GPSLongitudeRef')
    gps_altitude = metadata_dict.get('GPS GPSAltitude')
    # gps_altitude_ref = metadata_dict.get('GPS GPSAltitudeRef') 
    
    
    if not all([gps_latitude,gps_latitude_ref,gps_longitude,gps_longitude_ref,gps_altitude]):
        return None
    
    lat = ConvertMetadataCoordToDegrees(gps_latitude.values,gps_latitude_ref.values)
    lon = ConvertMetadataCoordToDegrees(gps_longitude.values,gps_longitude_ref.values)
    alt = float(gps_altitude.values[0].num) / float(gps_altitude.values[0].den)

    return lat,lon,alt

def MetadataToDataFrame(img_path):
    column_pattern = ['ID', 'Name', 'Date', 'Time', 'Lon', 'Lat', 'Altitude', 'North',
       'Azimuth', 'Cam. Maker', 'Cam. Model', 'Title', 'Comment', 'Path',
       'RelPath', 'Timestamp', 'Images', 'geometry']
    
    # Caso recursivo se o path for uma pasta
    if os.path.isdir(img_path):
        df_list = [MetadataToDataFrame(os.path.join(j)) for j in [os.path.join(dirpath,f) for (dirpath, dirnames, filenames) in os.walk(img_path) for f in filenames]]
        df = pd.concat([pd.DataFrame(columns=column_pattern)]+df_list,ignore_index=False)

        return df

    # Se não, caso geral
    metadata_dict = GetExifMetadata(img_path)

    # Apaga esse metadado muito grande para economizar espaço
    del metadata_dict["JPEGThumbnail"]

    df = pd.DataFrame.from_dict(metadata_dict,orient="index").T

    df[["Lat","Lon","Altitude"]] = df.apply(lambda row:GetCoord(row[[
        "GPS GPSLatitude",
        "GPS GPSLatitudeRef",
        "GPS GPSLongitude",
        "GPS GPSLongitudeRef",
        "GPS GPSAltitude"
    ]].to_dict()),axis=1,result_type="expand")

    df = df.rename(columns={
        
    })

    df["RelPath"] = df["Image ImageDescription"].apply(lambda value:value.values)
    df["Cam. Maker"] = df["Image Make"].apply(lambda value:value.values)
    df["Cam. Model"] = df["Image Model"].apply(lambda value:value.values)
    df["Name"] = df["RelPath"].apply(lambda value:os.path.basename(value))
    df["Date"] = df["EXIF DateTimeOriginal"].apply(lambda value:"/".join(reversed(value.values[:11].strip().split(":"))))
    df["Time"] = df["EXIF DateTimeOriginal"].apply(lambda value:value.values[11:].strip())
    df["Timestamp"] = pd.to_datetime(df["Date"].astype(str)+' '+df["Time"].astype(str), format=f'%d/%m/%Y %H:%M:%S')

    df = df[[i for i in column_pattern if i in df.columns]]

    return df

def KMZToGeoDataFrame(file_path,layer_name=None):
    # Arquivos pasta temporária, removida antes de retornar o valor
    temp_dir = "kmz_extract"
    os.makedirs(temp_dir, exist_ok=True)
    
    with zipfile.ZipFile(file_path, 'r') as kmz:
        kmz.extractall(temp_dir)
    
    kml_file = None
    for file in os.listdir(temp_dir):
        if file.endswith('.kml'):
            kml_file = os.path.join(temp_dir, file)
            break
    
    if not kml_file:
        raise FileNotFoundError("No KML file found in the KMZ archive")
    
    gdf = gpd.read_file(kml_file,driver='KML',layer=layer_name)

    shutil.rmtree(temp_dir)
    
    return gdf

def BuildAxis(gdf,sort_points,sort_point_column="Name"):
    if type(gdf["geometry"].iloc[0])==shapely.geometry.point.Point:
        pass
    if type(gdf["geometry"].iloc[0])==shapely.geometry.linestring.LineString:
        pass
    
    raise ValueError("Tipo de geometria incorreta!")

def CreateAxisFromGeoDataFrame(
        gdf,
        closest_point=None,
        start_meter_value=0,
        max_length=20,
        random=False,
        mean=0,
        max_diff=1,
        time_column=None,   # "Timestamp" to .gpkg from ImportPhotos QGIS
        return_type="line",
        tolerance=0.5):
    """
    Recebe o .gpkg tratado, gerado de diversas fontes, 
    como a extensão "ImportPhotos" do QGIS

    Retorna um geodataframe de pontos ou linhas
    "line" para a linha completa
    "point" para o ponto final da linha
    """
    valid_return_option = ["line","point"]
    if return_type not in valid_return_option:
        return ValueError(f"'{return_type}' inválido! Escolha entre {valid_return_option}")
            
    # Ordena os pontos para cria um eixo 
    gdf_sorted = SortPointsBySpaceTime(
        gdf,
        closest_point=closest_point,
        time_column=time_column,
        sort_column="ORDEM",
        distance_to_next_point_column="DISTANCIA"
    )

    # Cria um eixo com os pontos de campo e simplifica a geometria um pouco
    axis_line_string = shapely.LineString(gdf_sorted["geometry"].apply(lambda value:list(value.coords)[0]).tolist())
    if tolerance>0:
        axis_line_string = axis_line_string.simplify(tolerance=tolerance,preserve_topology=True)
    gdf_line_string = gpd.GeoDataFrame(geometry=[axis_line_string],crs="EPSG:31984")
    gdf_line_string["COMPRIMENTO"] = gdf_line_string.length.astype("float64")

    # Quebra o eixo em segmentos se reta e organiza um geodataframe
    list_segments = SplitLineStringByMaxLengthRandom(
        axis_line_string,
        max_length=max_length,
        random=random,
        mean=mean,
        max_diff=max_diff)
    
    gdf_segment = gpd.GeoDataFrame(geometry=list_segments,crs="EPSG:31984")
    # Calcula o KM acumulado do segmento
    gdf_segment["COMPRIMENTO"] = gdf_segment.length.astype("float64")
    gdf_segment["KM"] = start_meter_value + gdf_segment["COMPRIMENTO"].cumsum()/1000
    gdf_segment["KM"] = gdf_segment["KM"].round(3).astype("float64")

    # Se o formato de saída for ponto
    if return_type=="point":
        first_row = gpd.GeoDataFrame(
            {"COMPRIMENTO":[0],
             "KM":[0]},
            geometry=gdf_segment.iloc[0:1]["geometry"].apply(lambda value:shapely.Point(value.coords[0])),
            crs="EPSG:31984")
        gdf_segment["geometry"] = gdf_segment["geometry"].apply(lambda value:shapely.Point(value.coords[-1]))

        gdf_segment = gpd.GeoDataFrame(pd.concat([first_row,gdf_segment],ignore_index=True),geometry="geometry",crs="EPSG:31984")

    return gdf_line_string,gdf_segment

def CorrectKilometerPerStake(gdf,gdf_stake,kilometer_column="KM",length_column="COMPRIMENTO"):

    gdf = gdf.sjoin_nearest(gdf_stake[[kilometer_column,"geometry"]],how="left",max_distance=10).drop(columns=["index_right"])
    
    gdf[kilometer_column] = gdf[kilometer_column].fillna("-1+0")
    gdf[["pt1","pt2"]] = gdf[kilometer_column].str.split("+",expand=True)
    gdf[kilometer_column] = gdf["pt1"].astype(int) + gdf["pt2"].astype(int)/1000
    gdf = gdf.drop(columns=["pt1","pt2"])
    gdf[kilometer_column] = gdf[kilometer_column].replace(-1.0,np.nan)

    last_km = 0
    for index,row in gdf.iterrows():
        if np.isnan(row[kilometer_column]):
            row[kilometer_column] = last_km + round(row[length_column]/1000,3)
        
        last_km = row[kilometer_column]
        gdf.iloc[index] = row
    
    gdf[kilometer_column] = gdf[kilometer_column].round(3).astype("float64")

    return gdf

if __name__=="__main__":
    img_path = r"C:\Users\User\Desktop\Repositórios Locais\irap-data-processing\data\img\350ECE0090S0"
    axis_path = r"C:\Users\User\Desktop\Repositórios Locais\irap-data-processing\test\BR\080BGO0130D.gpkg"
   
    # result = MetadataToDataFrame(path)
    gdf = KMZToGeoDataFrame("test/BR/SNV - BR-080 atual.kmz").to_crs(31984)
    gdf["geometry"] = gdf['geometry'].apply(shapely.force_2d).to_crs(31984)
    fp = gdf[gdf["Name"]=="94+300"]["geometry"].values[0]
    
    # df = MetadataToDataFrame(img_path)
    # gdf = gpd.GeoDataFrame(
    #     df,
    #     geometry=gpd.points_from_xy(df["Lon"],df["Lat"]),
    #     crs="EPSG:4326").to_crs(31984)
    # print(gdf)
    # fp = gdf[gdf["Name"]=="G0073135.JPG"]["geometry"].values[0]

    _,segment = CreateAxisFromGeoDataFrame(
        gdf,
        closest_point=fp,
        start_meter_value=0,
        max_length=20,
        return_type="point",
        tolerance=0)

    segment.to_file("test/BR/axis_processed.gpkg",driver="GPKG",index=False)
    segment = gpd.read_file("test/BR/axis_processed.gpkg").to_crs(31984)
    gdf_stake = KMZToGeoDataFrame("test/BR/SNV - BR-080 atual.kmz")
    segment = CorrectKilometerPerStake(segment,gdf,kilometer_column="Name")
    segment.to_file("test/BR/axis_processed_corrigido.gpkg",driver="GPKG",index=False)
    print(segment.tail(50))