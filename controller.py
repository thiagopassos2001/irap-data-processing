from model import BuildAxis,KMZToGeoDataFrame
import streamlit as st
import geopandas as gpd
from io import BytesIO

def DownloadBuildAxis(axis_path,stake_path,start_point_label,start_name_column,CRS):
    # with st.spinner("Processando...", show_time=True):

    print("Iniciando processo...")

    CRS_int = int(CRS.split(":")[-1])
    gdf_axis = gpd.read_file(axis_path).to_crs(CRS_int)
    gdf_axis_stake = KMZToGeoDataFrame(stake_path).to_crs(CRS_int)

    print(gdf_axis)
    
    gdf_axis,gdf_axis_stake = BuildAxis(
        gdf_axis,
        gdf_axis_stake,
        start_point_label,
        start_name_column,
        CRS)
    st.success("Arquivo processado com sucesso!")

    buffer0 = BytesIO()
    gdf_axis.to_file(buffer0,driver='GPKG',index=False)
    buffer0.seek(0)

    buffer1 = BytesIO()
    gdf_axis_stake.to_file(buffer1,driver='GPKG',index=False)
    buffer1.seek(1)

    return buffer0,buffer1