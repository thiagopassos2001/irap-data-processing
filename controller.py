from model import *
import streamlit as st
import geopandas as gpd
from io import BytesIO

def ProcessAxisAndSheet(
        axis_path,
        stake_path,
        img_path,
        start_point_label,
        start_name_column,
        CRS):
    # with st.spinner("Processando...", show_time=True):

    print("Iniciando processo...")
    st.success("Iniciando processo...",)

    gdf_axis = gpd.read_file(axis_path).to_crs(CRS)
    gdf_axis_stake = KMZToGeoDataFrame(stake_path).to_crs(CRS)
    gdf_img = gpd.read_file(img_path).to_crs(CRS)
    df_ref = pd.read_excel("file/img_ref_pattern.xlsx")
    
    gdf_axis,gdf_axis_stake = BuildAxis(
        gdf_axis,
        gdf_axis_stake,
        start_point_label,
        start_name_column,
        CRS)
    
    gdf_axis = MatchImages(gdf_axis,gdf_img)
    sheet_ref = SheetRef(gdf_axis,df_ref)
    
    print("Arquivo processado com sucesso!")
    st.success("Arquivo processado com sucesso!")

    gdf_axis_buffer = BytesIO()
    gdf_axis.to_file(gdf_axis_buffer,driver='GPKG',index=False)
    gdf_axis_buffer.seek(0)

    gdf_axis_stake_buffer = BytesIO()
    gdf_axis_stake.to_file(gdf_axis_stake_buffer,driver='GPKG',index=False)
    gdf_axis_stake_buffer.seek(0)

    sheet_ref_buffer = BytesIO()
    sheet_ref.to_excel(sheet_ref_buffer,index=False)
    sheet_ref_buffer.seek(0)

    return gdf_axis_buffer,gdf_axis_stake_buffer,sheet_ref_buffer