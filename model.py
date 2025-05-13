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

# CRS = "EPSG:31982" # Goiás Teste
# CRS_int = int(CRS.split(":")[-1])

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
        tolerance=0.5,):
    """
    Recebe o .gpkg tratado, gerado de diversas fontes, 
    como a extensão "ImportPhotos" do QGIS

    Retorna um geodataframe de pontos ou linhas
    "line" para a linha completa
    "point" para o ponto final da linha
    """
    crs_gdf = gdf.crs

    valid_return_option = ["line","point"]
    if return_type not in valid_return_option:
        return ValueError(f"'{return_type}' inválido! Escolha entre {valid_return_option}")
    
    if not gdf.geom_type.unique()[0]!=shapely.Point:
        raise ValueError(f"Tipo de geometria {gdf.geom_type.unique()[0]} não compatível!")
    
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
    gdf_line_string = gpd.GeoDataFrame(geometry=[axis_line_string],crs=crs_gdf)
    gdf_line_string["COMPRIMENTO"] = gdf_line_string.length.astype("float64")

    # Quebra o eixo em segmentos se reta e organiza um geodataframe
    list_segments = SplitLineStringByMaxLengthRandom(
        axis_line_string,
        max_length=max_length,
        random=random,
        mean=mean,
        max_diff=max_diff)
    
    gdf_segment = gpd.GeoDataFrame(geometry=list_segments,crs=crs_gdf)
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
            crs=crs_gdf)
        gdf_segment["geometry"] = gdf_segment["geometry"].apply(lambda value:shapely.Point(value.coords[-1]))

        gdf_segment = gpd.GeoDataFrame(pd.concat([first_row,gdf_segment],ignore_index=True),geometry="geometry",crs=crs_gdf)

    return gdf_line_string,gdf_segment

def ExpandToSegmentsByMaxLengthRandom(
        gdf,
        max_length=20.0,
        closest_point=None,
        random=False,
        mean=0,
        max_diff=1,
    ):

    new_gdf = []

    for index, row in gdf.iterrows():
        line = row["geometry"]
        if closest_point!=None:
            start_pt = shapely.Point(list(line.coords)[0])
            last_pt = shapely.Point(list(line.coords)[-1])
            if shapely.distance(start_pt,closest_point)<shapely.distance(last_pt,closest_point):
                line = line
                closest_point = last_pt
            else:
                line = shapely.LineString(reversed(list(line.coords)))
                closest_point = start_pt
        
        list_segments = SplitLineStringByMaxLengthRandom(
            row["geometry"],
            max_length=max_length,
            random=random,
            mean=mean,
            max_diff=max_diff)
        
        for segment in list_segments:
            new_row = row.copy()
            new_row["geometry"] = segment
            new_gdf.append(new_row)
    
    new_gdf = gpd.GeoDataFrame(new_gdf,columns=gdf.columns,crs=gdf.crs)
    
    return new_gdf

def SplitLineStringByPoints(line,points_list,max_dist_snap=20,offset_dist=1e-5):
    """
    Usa linhas paralelas à linha original para cortar,
    Mesmo depois de projetar o ponto, podem existir imprecisões geométricas
    Nesse sentido, projeta-se o ponto nas linhas paralelas e cria uma perpendicular
    Que invariavelmente corta a princial

    offset_dist < max_dist_snap
    """

    if offset_dist>=max_dist_snap:
        return ValueError(f"{offset_dist} deve ser menor que {offset_dist}.")

    valid_parallel_line = []
    left_line,right_line = line.parallel_offset(offset_dist,"left"),line.parallel_offset(offset_dist,"right")
    
    for pt in points_list:
        dist_pt_line = line.distance(pt)
        if dist_pt_line <= max_dist_snap:
            left_pt_interpolate = left_line.interpolate(line.project(pt))
            right_pt_interpolate = right_line.interpolate(line.project(pt))

            valid_parallel_line.append(
                shapely.LineString([(left_pt_interpolate.x,left_pt_interpolate.y),(right_pt_interpolate.x,right_pt_interpolate.y)]))
    
    if not valid_parallel_line:
        return [line]

    segments = shapely.ops.split(line, shapely.MultiLineString(valid_parallel_line))
    segments = list(segments.geoms) if segments.geoms else [line]

    min_length = offset_dist*0.75
    segments = [i for i in segments if i.length>min_length]
    
    return segments

def ExpandToSegmentsBySplitPoint(
        gdf,
        points_list,
        max_dist_snap=20,
        offset_dist=1e-5,
    ):

    new_gdf = []

    for index, row in gdf.iterrows():
        list_segments = SplitLineStringByPoints(
            row["geometry"],
            points_list,
            max_dist_snap=max_dist_snap,
            offset_dist=offset_dist)
        
        for segment in list_segments:
            new_row = row.copy()
            new_row["geometry"] = segment
            new_gdf.append(new_row)
    
    new_gdf = gpd.GeoDataFrame(new_gdf,columns=gdf.columns,crs=gdf.crs)
    
    return new_gdf

def ExpandLineStringToPoint(gdf,drop_duplicates=True):

    new_gdf = []

    for index, row in gdf.iterrows():
        list_segments = list(row["geometry"].coords)
        
        for segment in list_segments:
            new_row = row.copy()
            new_row["geometry"] = shapely.Point(segment)
            new_gdf.append(new_row)
    
    new_gdf = gpd.GeoDataFrame(new_gdf,columns=gdf.columns,crs=gdf.crs)

    if drop_duplicates:
        new_gdf = new_gdf.drop_duplicates(subset="geometry")

    return new_gdf

def CorrectKilometerPerStake(gdf,gdf_stake,kilometer_column="KM ESTACA",length_column="COMPRIMENTO"):

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

def StakeToFloat(stake_string,sep="+"):
    km,meter = stake_string.split(sep)
    return round(int(km)+int(meter)/1000,3)

def BuildAxis(gdf_axis,gdf_stake,start_point_label,start_name_column,CRS):
    # Estaca
    # gdf_stake = KMZToGeoDataFrame(stake_path).to_crs(CRS_int)
    gdf_stake['geometry'] = gdf_stake['geometry'].apply(shapely.force_2d)
    gdf_stake["KM ESTACA"] = gdf_stake[start_name_column].apply(StakeToFloat)
    start_point = gdf_stake[gdf_stake[start_name_column]==start_point_label]["geometry"].values[0]

    # Eixo
    # axis_name_file = os.path.basename(axis_path)
    # gdf_axis = gpd.read_file(axis_path).to_crs(CRS_int)
    gdf_axis['geometry'] = gdf_axis['geometry'].apply(shapely.force_2d)

    # Inverte ou não a ordem dos KMs
    line = gdf_axis["geometry"].tolist()[0]
    pt_start = shapely.Point(list(line.coords)[0])
    pt_last = shapely.Point(list(line.coords)[-1])

    if shapely.distance(start_point,pt_start)>shapely.distance(start_point,pt_last):
        gdf_axis.loc[0,"geometry"] = shapely.LineString(reversed(list(line.coords)))
    gdf_axis = ExpandToSegmentsBySplitPoint(gdf_axis,gdf_stake["geometry"].tolist(),max_dist_snap=100)
    gdf_axis["COMPRIMENTO"] = gdf_axis["geometry"].length
    # gdf_axis.to_file(axis_path.replace(".gpkg"," EIXO ESTAQUEADO.gpkg"),index=False)
    gdf_axis_stake = gdf_axis.copy()

    new_gdf_axis = []
    count = 0
    max_count = len(gdf_axis)

    next_point = start_point
    while not gdf_axis.empty:
        stake_start = gdf_stake.copy()
        stake_start["NEXT STAKE"] = stake_start["geometry"].apply(lambda value:shapely.distance(value,next_point))
        stake_start = stake_start.sort_values(by="NEXT STAKE").iloc[:1]

        next_point = stake_start["geometry"].values[0]

        axis = gdf_axis.copy()
        axis["NEXT AXIS"] = axis["geometry"].apply(lambda value:shapely.distance(value,next_point))
        axis = axis.sort_values("NEXT AXIS").iloc[:1]

        # Remove do todo
        gdf_axis = gdf_axis[gdf_axis["geometry"]!=axis["geometry"].iloc[0]]
        
        # Comprimento
        l = axis["geometry"].iloc[0].length
        num_pt = round(l/20,0) if round(l/20,0)<= 50 else 50
        len_split = l/num_pt

        # Converte para ponto
        axis = ExpandLineStringToPoint(axis)

        # Cria o eixo
        _, axis = CreateAxisFromGeoDataFrame(
            axis,
            closest_point=next_point,
            return_type="point",
            max_length=len_split,
            tolerance=0)
        
        axis["KM"] = axis["KM"]*(1 if l<=1000 else 1000/l) + stake_start["KM ESTACA"].values[0]
        axis["KM"] = axis["KM"].round(3)
        
        new_gdf_axis.append(axis)
        count = count + 1
        next_point = axis["geometry"].values[0]

        print(f"Running\t{round(count*100/max_count,1)}%")
    
    gdf_axis = gpd.GeoDataFrame(pd.concat(new_gdf_axis,ignore_index=True),geometry="geometry",crs=CRS)
    gdf_axis = gdf_axis.drop_duplicates(subset="geometry",keep="last").reset_index()
    gdf_axis["ORDEM"] = list(range(1,len(gdf_axis)+1))

    return gdf_axis,gdf_axis_stake

def MatchImages(gdf_axis,gdf_img):
    gdf_axis = gdf_axis.sjoin_nearest(
        gdf_img[["Name","RelPath","Timestamp","Lon","Lat","geometry"]],
        how="left",
        max_distance=20,
        distance_col="DISTANCIA IMAGEM").sort_values(by="DISTANCIA IMAGEM")
    
    gdf_axis = gdf_axis.drop_duplicates(subset="index_right")
    gdf_axis = gdf_axis.drop(columns=["index_right"])
    gdf_axis = gdf_axis.dropna(subset="DISTANCIA IMAGEM")
    gdf_axis = gdf_axis.sort_values(by="ORDEM").reset_index()
    gdf_axis["ORDEM"] = list(range(0,len(gdf_axis)))

    gdf_axis["DIV LINHA"] = gdf_axis["ORDEM"].apply(lambda value:value//5)
    gdf_axis["DIV PLANILHA"] = gdf_axis["ORDEM"].apply(lambda value:value//500)
    
    return gdf_axis

def SheetRef(gdf_axis,df_ref):

    gdf_first = gdf_axis.copy().drop_duplicates(subset="DIV LINHA",keep="first")
    gdf_axis = gdf_axis[-gdf_axis["ORDEM"].isin(gdf_first["ORDEM"].tolist())]

    df = [df_ref]
    for index,row in gdf_first.iterrows():
        df_ = pd.DataFrame()
        df_["Image reference"] = [row["Name"]]
        df_["centre - 0"] = [row["Name"]]
        df_["Latitude"] = [row["Lat"]]
        df_["Longitude"] = [row["Lon"]]

        for i,j in zip(gdf_axis[gdf_axis["DIV LINHA"]==row["DIV LINHA"]]["Name"].tolist(),["2","4","6","8"]):
            df_[f"centre - {j}0"] = [i]

        df.append(df_)
    
    df = pd.concat(df,ignore_index=True)

    return df

if __name__=="__main__":
    img_path = "test/BR/fotos/SNV - BR-080 - Fotos.gpkg"
    axis_path = "test/BR/eixo/SINV - BR - 080 - Linha.gpkg"
    stake_path = "test/BR/eixo/SNV - BR-080 - Estacas (contratante).kmz"
    ref_path =  "file/img_ref_pattern.xlsx"
    start_point_label = "94+300"
    start_name_column = "Name"
    max_sheet_km = 10
    CRS = "EPSG:31982" # Goiás Teste

    gdf_axis,gdf_axis_stake = BuildAxis(
        gpd.read_file(axis_path).to_crs(CRS),
        KMZToGeoDataFrame(stake_path).to_crs(CRS),
        start_point_label,
        start_name_column,
        CRS
        )
    # gdf_axis.to_file("test/BR/eixo/Estaqueamento 20m.gpkg",index=False)
    
    gdf_axis = MatchImages(gdf_axis,gpd.read_file(img_path).to_crs(CRS))
    sheet_ref = SheetRef(gdf_axis,pd.read_excel(ref_path))

    # gdf_axis.to_file("test/BR/eixo/Teste.gpkg",index=False)
    # sheet_ref.to_excel("test/BR/PlanRef.xlsx",index=False)
    
    print(gdf_axis.head(50)) # .columns

    if False:
        # Estaca
        gdf_stake = KMZToGeoDataFrame(stake_path).to_crs(CRS_int)
        gdf_stake['geometry'] = gdf_stake['geometry'].apply(shapely.force_2d)
        gdf_stake["KM ESTACA"] = gdf_stake[start_name_column].apply(StakeToFloat)
        start_point = gdf_stake[gdf_stake[start_name_column]==start_point_label]["geometry"].values[0]

        # Eixo
        axis_name_file = os.path.basename(axis_path)
        gdf_axis = gpd.read_file(axis_path).to_crs(CRS_int)
        gdf_axis['geometry'] = gdf_axis['geometry'].apply(shapely.force_2d)

        # Inverte ou não a ordem dos KMs
        line = gdf_axis["geometry"].tolist()[0]
        pt_start = shapely.Point(list(line.coords)[0])
        pt_last = shapely.Point(list(line.coords)[-1])

        if shapely.distance(start_point,pt_start)>shapely.distance(start_point,pt_last):
            gdf_axis.loc[0,"geometry"] = shapely.LineString(reversed(list(line.coords)))
        gdf_axis = ExpandToSegmentsBySplitPoint(gdf_axis,gdf_stake["geometry"].tolist(),max_dist_snap=100)
        gdf_axis["COMPRIMENTO"] = gdf_axis["geometry"].length
        gdf_axis_stake = gdf_axis.copy()
        # gdf_axis.to_file(axis_path.replace(".gpkg"," EIXO ESTAQUEADO.gpkg"),index=False)

        new_gdf_axis = []
        count = 0
        next_point = start_point
        while not gdf_axis.empty:
            stake_start = gdf_stake.copy()
            stake_start["NEXT STAKE"] = stake_start["geometry"].apply(lambda value:shapely.distance(value,next_point))
            stake_start = stake_start.sort_values(by="NEXT STAKE").iloc[:1]

            next_point = stake_start["geometry"].values[0]

            axis = gdf_axis.copy()
            axis["NEXT AXIS"] = axis["geometry"].apply(lambda value:shapely.distance(value,next_point))
            axis = axis.sort_values("NEXT AXIS").iloc[:1]

            # Remove do todo
            gdf_axis = gdf_axis[gdf_axis["geometry"]!=axis["geometry"].iloc[0]]
            
            # Comprimento
            l = axis["geometry"].iloc[0].length
            num_pt = round(l/20,0) if round(l/20,0)<= 50 else 50
            len_split = l/num_pt

            # Converte para ponto
            axis = ExpandLineStringToPoint(axis)

            # Cria o eixo
            _, axis = CreateAxisFromGeoDataFrame(
                axis,
                closest_point=next_point,
                return_type="point",
                max_length=len_split,
                tolerance=0)
            
            axis["KM"] = axis["KM"]*(1 if l<=1000 else 1000/l) + stake_start["KM ESTACA"].values[0]
            axis["KM"] = axis["KM"].round(3)
            
            new_gdf_axis.append(axis)
            count = count + 1
            next_point = axis["geometry"].values[0]

            print(count,stake_start["KM ESTACA"].iloc[0])
        
        gdf_axis = gpd.GeoDataFrame(pd.concat(new_gdf_axis,ignore_index=True),geometry="geometry",crs=CRS)
        gdf_axis = gdf_axis.drop_duplicates(subset="geometry",keep="last")

        gdf_axis.to_file(axis_path.replace(".gpkg"," EIXO ESTAQUEADO 20m.gpkg"),index=False)
        print(gdf_axis)
        print("Arquivo Salvo!")
