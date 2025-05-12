import streamlit as st

from controller import DownloadBuildAxis
import subprocess

def main():
    st.title("Coleta de Dados - Pré Tratamento",)
    st.image("assets/capa.jpg", caption="Segmentação de imagens ao longo do eixo da rodovia orientado ao estaqueamento")
    CRS = st.text_input("Coordinate Reference System (CRS) do Local (sistema métrico, padrão como no exemplo)",value="EPSG:31982")

    stake_path = st.file_uploader("Escolha o shapefile do estaqueamento do eixo (.kmz)", type=["kmz"])
    axis_path = st.file_uploader("Escolha o shapefile do caminho do eixo (.gpkg). Pode ser coletado pelo MyMaps", type=["gpkg"])

    start_name_column = st.text_input("Nome da coluna que contém a estaca inicial do estaqueamento",value="Name")
    start_point_label = st.text_input("Número da estaca inicial (padrão como no exemplo)",value="0+000")

    if st.button("Processar Dados"):
        if (stake_path is not None) and (axis_path is not None) and (start_point_label is not None):
            try:
                with st.status("Processando arquivos...", expanded=True,state="running",) as status:
                    gdf_axis,gdf_axis_stake = DownloadBuildAxis(
                        axis_path,
                        stake_path,
                        start_point_label,
                        start_name_column,
                        CRS
                        )
                    status.update(label="Processing complete!", state="complete", expanded=False)
                    
                    st.session_state["gdf_axis"] = gdf_axis.getvalue()
                    st.session_state["gdf_axis_stake"] = gdf_axis_stake.getvalue()

            except Exception as e:
                print(f"Erro: {e}")

    if "gdf_axis_stake" in st.session_state:
        st.download_button(
            label="Download - Estaqueamento nos Marcos de 1km",
            data=st.session_state["gdf_axis_stake"],
            file_name="Estaqueamento 1km.gpkg",
            mime="gpkg",
            help="Baixar Estaqueamento 1km"
        )
    
    if "gdf_axis" in st.session_state:
        st.download_button(
            label="Download - Estaqueamento a cada 20m",
            data=st.session_state["gdf_axis"],
            file_name="Estaqueamento 20m.gpkg",
            mime="gpkg",
            help="Baixar Estaqueamento 20m"
            )

if __name__=="__main__":
    # subprocess.run(["pip","install","-r","requirements.txt"])
    main()