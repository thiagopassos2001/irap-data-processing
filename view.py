import streamlit as st
from controller import DownloadBuildAxis
import subprocess

def main():
    st.title("iRap - Pré Tratamento de Dados")
    
    stake_path = st.file_uploader("Escolha o shapefile de estaca (.kmz) do eixo", type=["kmz"])
    start_name_column = st.text_input("Qual o nome da coluna da estaca inicial",value="Name")
    start_point_label = st.text_input("Qual o nome da estaca inicial")

    axis_path = st.file_uploader("Escolha o shapefile (.gpkg) do eixo", type=["gpkg"])

    if st.button("Processar Dados"):
        if (stake_path is not None) and (axis_path is not None) and (start_point_label is not None):
            try:
                gdf_axis,gdf_axis_stake = DownloadBuildAxis(
                    axis_path,
                    stake_path,
                    start_point_label,
                    start_name_column
                )

                st.download_button(
                    label="Download ESTAQUEAMENTO",
                    data=gdf_axis_stake,
                    file_name="ESTAQUEAMENTO.gpkg",
                    mime="gpkg",
                    help="Baixar ESTAQUEAMENTO"
                )

                st.download_button(
                    label="Download ESTAQUEAMENTO 20m",
                    data=gdf_axis,
                    file_name="ESTAQUEAMENTO 20m.gpkg",
                    mime="gpkg",
                    help="Baixar ESTAQUEAMENTO 20m"
                )

            except Exception as e:
                print(f"Erro: {e}")
        # axis = GetBuildAxis()
        
        # # Exibe resultados
        # st.header("Resultados")
        # st.subheader("Dados Processados")
        # st.write(processed)
        
        # st.subheader("Análise")
        # st.write(analysis)


if __name__=="__main__":
    subprocess.run(["pip","install","-r","requirements.txt"])
    main()