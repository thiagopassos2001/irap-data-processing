from model import BuildAxis
import streamlit as st

def DownloadBuildAxis(axis_path,stake_path,start_point_label,start_name_column):
    # with st.spinner("Processando...", show_time=True):
    print("Iniciando...")
    gdf_axis,gdf_axis_stake = BuildAxis(axis_path,stake_path,start_point_label,start_name_column)
    st.success("Arquivo processado com sucesso!")
    
    gdf_axis_stake = gdf_axis_stake.to_file(axis_path.replace(".gpkg"," EIXO ESTAQUEADO.gpkg"),index=False)
    gdf_axis = gdf_axis.to_file(axis_path.replace(".gpkg"," EIXO ESTAQUEADO 20m.gpkg"),index=False)

    return gdf_axis,gdf_axis_stake