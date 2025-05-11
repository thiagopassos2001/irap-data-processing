import streamlit as st

from controller import DownloadBuildAxis
import subprocess

def main():
    st.title("iRap - Pré Tratamento de Dados")
    CRS = st.text_input("CRS do local (tipo SIRGAS 2000)",value="EPSG:31982")
    CRS_int = int(CRS.split(":")[-1])

    stake_path = st.file_uploader("Escolha o shapefile de estaca (.kmz) do eixo", type=["kmz"])
    start_name_column = st.text_input("Qual o nome da coluna da estaca inicial",value="Name")
    start_point_label = st.text_input("Qual o nome da estaca inicial")

    axis_path = st.file_uploader("Escolha o shapefile (.gpkg) do eixo", type=["gpkg"])
    

    if st.button("Processar Dados"):
        if (stake_path is not None) and (axis_path is not None) and (start_point_label is not None):
            try:
                with st.status("Processing GeoPackage file...", expanded=True) as status:
                    gdf_axis,gdf_axis_stake = DownloadBuildAxis(
                        axis_path,
                        stake_path,
                        start_point_label,
                        start_name_column,
                        CRS
                        )
                    status.update(label="Processing complete!", state="complete", expanded=False)
                    st.session_state.gdf_axis = gdf_axis.getvalue()
                    st.session_state.gdf_axis_stake = gdf_axis_stake.getvalue()

            except Exception as e:
                print(f"Erro: {e}")

    if st.session_state.gdf_axis_stake is not None:
        st.download_button(
            label="Download ESTAQUEAMENTO 20m",
            data=st.session_state.gdf_axis_stake,
            file_name="ESTAQUEAMENTO 20m.gpkg",
            mime="gpkg",
            help="Baixar ESTAQUEAMENTO 20m"
        )
    
    if st.session_state.gdf_axis is not None:
        st.download_button(
            label="Download ESTAQUEAMENTO",
            data=st.session_state.gdf_axis,
            file_name="ESTAQUEAMENTO.gpkg",
            mime="gpkg",
            help="Baixar ESTAQUEAMENTO"
            )

if __name__=="__main__":
    # subprocess.run(["pip","install","-r","requirements.txt"])
    main()