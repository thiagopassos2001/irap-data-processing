import geopandas as gpd
import os
import shutil
import subprocess
import timeit
import tkinter as tk
from tkinter import filedialog

def OpenFileDialog():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename()    
    
    root.destroy()
    
    return file_path

def OpenFolderDialog():
    root = tk.Tk()
    root.withdraw()
    folder_path = filedialog.askdirectory()
    
    root.destroy()
    
    return folder_path

from until import MoveOrCopyFiles

if  __name__ == "__main__":
    print("Arquivo .gpkg com o eixo tratado: ")
    input_gpkg_file = OpenFileDialog()
    print(input_gpkg_file)
    
    print("Pasta de origem: ")
    root_input_path = OpenFolderDialog()
    print(root_input_path)
    
    print("Pasta de destino: ")
    root_output_path = OpenFolderDialog()
    print(root_output_path)

    # Modo "move" ou "copy"
    mode = 'copy'

    gdf = gpd.read_file(input_gpkg_file)
    gdf['src'] = gdf['RelPath'].apply(lambda x:os.path.join(root_input_path,"/".join(x.split("/")[-2:])).replace("\\","/"))
    gdf['dst'] = gdf['RelPath'].apply(lambda x:os.path.join(root_output_path,"/".join(x.split("/")[-2:])).replace("\\","/"))

    # Inicia o timer
    start_timer = timeit.default_timer()
    max_count = len(gdf)
    count_progress = 0
    
    for index, row in gdf.iterrows():
        src = row['src']
        dst = row['dst']
        try:
            dst = MoveOrCopyFiles(src=src,dst=dst,mode=mode,replace_file=False,logs=False,return_dst=True)
        except Exception as e:
            print(e)
        
        # Estimativa de tempo médio
        count_progress = count_progress + 1
        stop_timer = timeit.default_timer()
        count_timer = stop_timer - start_timer
        eta = (count_timer/(count_progress))*(max_count-count_progress)
        print(f"{os.path.basename(dst)} foi {'movido.' if mode=='move' else 'copiado.'}... {count_progress}/{max_count} (Run: {int(count_timer/60)}min:{int(count_timer%60)}s - ETC:{int(eta/60)}min:{int(eta%60)}s)")