from model import BuildAxis,KMZToGeoDataFrame
import streamlit as st
import geopandas as gpd
from io import BytesIO

def DownloadBuildAxis(axis_path,stake_path,start_point_label,start_name_column,CRS):
    # with st.spinner("Processando...", show_time=True):

    print("Iniciando processo...")
    st.success("Iniciando processo...",)

    gdf_axis = gpd.read_file(axis_path).to_crs(CRS)
    gdf_axis_stake = KMZToGeoDataFrame(stake_path).to_crs(CRS)

    print(gdf_axis)
    
    gdf_axis,gdf_axis_stake = BuildAxis(
        gdf_axis,
        gdf_axis_stake,
        start_point_label,
        start_name_column,
        CRS)
    
    print("Arquivo processado com sucesso!")
    st.success("Arquivo processado com sucesso!")

    gdf_axis_buffer = BytesIO()
    gdf_axis.to_file(gdf_axis_buffer,driver='GPKG',index=False)
    gdf_axis_buffer.seek(0)

    gdf_axis_stake_buffer = BytesIO()
    gdf_axis_stake.to_file(gdf_axis_stake_buffer,driver='GPKG',index=False)
    gdf_axis_stake_buffer.seek(1)

    return gdf_axis_buffer,gdf_axis_stake_buffer