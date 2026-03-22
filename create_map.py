import folium
from folium.plugins import TagFilterButton
import pandas as pd
import numpy as np
import branca.colormap as cmp
import matplotlib.pyplot as plt
import matplotlib.tri as tri
import base64
from io import BytesIO
from folium import Element, FeatureGroup, LayerControl, raster_layers
import webbrowser

def plot_to_base64():
    """Konwertuje aktualny wykres matplotlib do formatu base64 dla HTML."""
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close()
    return image_base64

def generate_statistics(coords_df, detector_df):
    """Generuje sekcję HTML z wykresami i statystykami ogólnymi."""
    stats_html = """
    <style>
        .stat-section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 8px; background: #f9f9f9; font-family: Arial; }
        h2 { color: #2c3e50; }
        h3 { color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
    </style>
    <h2>Statystyki pomiarowe radonu</h2>
    """
    
    densities = []
   
    for did in coords_df["clean_id"]:
        if did == "HA4116" or did not in detector_df.index:
            continue
        try:
            val = float(detector_df.loc[did, "Stężenie radonu"])
            densities.append(val)
        except:
            continue

    if densities:
        plt.figure(figsize=(10, 6))
        plt.hist(densities, bins=20, alpha=0.7, color='skyblue', edgecolor='black')
        plt.title('Rozkład stężenia radonu (wszystkie punkty)')
        plt.xlabel('Stężenie [Bq/m³]')
        plt.ylabel('Liczba detektorów')
        plt.grid(True, alpha=0.3)
        hist_base64 = plot_to_base64()
        
        stats_html += f"""
        <div class="stat-section">
            <h3>Podsumowanie zbiorcze</h3>
            <p><b>Średnia arytmetyczna:</b> {np.mean(densities):.2f} Bq/m³</p>
            <p><b>Mediana:</b> {np.median(densities):.2f} Bq/m³</p>
            <p><b>Odchylenie standardowe:</b> {np.std(densities):.2f} Bq/m³</p>
            <p><b>Zakres wartości:</b> {np.min(densities):.1f} - {np.max(densities):.1f} Bq/m³</p>
            <img src="data:image/png;base64,{hist_base64}" style="width:100%; max-width:600px; display: block; margin: 0 auto;">
        </div>
        """
    return stats_html

def add_triangulation_layer(m, coords_df, detector_df, vmin, vmax):
    """Tworzy interpolowaną warstwę kolorystyczną na podstawie punktów."""
    data = []
    for i in range(len(coords_df)):
        did = coords_df.iloc[i]["clean_id"]
        if did == "HA4116" or did not in detector_df.index:
            continue
        try:
            val = float(detector_df.loc[did, "Stężenie radonu"])
            lat = coords_df.iloc[i]["Latitude"]
            lon = coords_df.iloc[i]["Longitude"]
            if not (np.isnan(lat) or np.isnan(lon)):
                data.append([lon, lat, val])
        except:
            continue

    data_arr = np.array(data)
    if len(data_arr) < 3:
        return

    x, y, z = data_arr[:, 0], data_arr[:, 1], data_arr[:, 2]
    triang = tri.Triangulation(x, y)


    threshold = 0.15
    mask = []
    for t in triang.triangles:
        d1 = np.sqrt((x[t[0]]-x[t[1]])**2 + (y[t[0]]-y[t[1]])**2)
        d2 = np.sqrt((x[t[1]]-x[t[2]])**2 + (y[t[1]]-y[t[2]])**2)
        d3 = np.sqrt((x[t[2]]-x[t[0]])**2 + (y[t[2]]-y[t[0]])**2)
        mask.append(d1 > threshold or d2 > threshold or d3 > threshold)
    triang.set_mask(mask)

    plt.ioff()
    margin = 0.05
    xlim = [min(x)-margin, max(x)+margin]
    ylim = [min(y)-margin, max(y)+margin]
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_xlim(xlim); ax.set_ylim(ylim); ax.axis('off')

    levels = np.linspace(vmin, vmax, 50)
    ax.tricontourf(triang, z, levels=levels, cmap='RdYlBu_r', alpha=0.6, extend='both')

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
    img_str = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close()

    interp_fg = FeatureGroup(name="Mapa stężeń (Interpolacja)", show=True)
    raster_layers.ImageOverlay(
        image=img_str,
        bounds=[[ylim[0], xlim[0]], [ylim[1], xlim[1]]],
        opacity=0.75, interactive=False, zindex=1
    ).add_to(interp_fg)
    interp_fg.add_to(m)


try:
   
    p1 = r"C:\Users\jakub\radon_2\DETEKTORY_DANE_18_10_2025.xlsx"
    coords_df = pd.read_excel(p1, sheet_name="Sheet1").dropna(subset=["Latitude", "Longitude"])
    
    coords_df["clean_id"] = coords_df["Nr detektora"].astype(str).str.replace(r"\s+", "", regex=True)

    
    p2 = r"C:\Users\jakub\radon_2\Bozon-2026.xlsx"
    bozon_file = pd.ExcelFile(p2)
    all_results = []
    for sn in bozon_file.sheet_names:
        df_tmp = pd.read_excel(p2, sheet_name=sn)
        if "Detector ID" in df_tmp.columns:
            all_results.append(df_tmp)
    
    detector_df = pd.concat(all_results, ignore_index=True)
    
   
    detector_df["Detector ID"] = detector_df["Detector ID"].astype(str).str.replace(r"\s+", "", regex=True)
    
   
    if "Track density" in detector_df.columns:
        detector_df["Stężenie radonu"] = pd.to_numeric(detector_df["Track density"], errors='coerce')
    
    
    detector_df = detector_df.groupby("Detector ID")["Stężenie radonu"].mean().dropna().to_frame()

   
    valid_vals = []
    for cid in coords_df["clean_id"]:
        if cid in detector_df.index and cid != "HA4116":
            valid_vals.append(detector_df.loc[cid, "Stężenie radonu"])
    
    g_min, g_max = (min(valid_vals), max(valid_vals)) if valid_vals else (0, 300)

except Exception as e:
    print(f"Błąd krytyczny danych: {e}")
    exit()


m = folium.Map([50.06, 19.94], zoom_start=10, tiles="OpenStreetMap")

colormap = cmp.LinearColormap(
    colors=['blue', 'cyan', 'green', 'yellow', 'orange', 'red'],
    vmin=g_min, vmax=g_max,
    caption="Stężenie radonu [Bq/m³]"
)
colormap.add_to(m)

def get_clr(v):
    if g_max == g_min: return "green"
    n = (v - g_min) / (g_max - g_min)
    if n < 0.2: return "blue"
    if n < 0.4: return "green"
    if n < 0.6: return "orange"
    if n < 0.8: return "red"
    return "black"


st_html = generate_statistics(coords_df, detector_df)
m.get_root().html.add_child(Element(f"""
<div style="position: fixed; top: 100px; right: 10px; z-index: 1000;">
    <button onclick="document.getElementById('mStat').style.display='block'" 
    style="background: #8e44ad; color: white; border: none; padding: 12px; border-radius: 6px; cursor: pointer; writing-mode: vertical-rl; height: 140px; font-weight: bold;">
        STATYSTYKI POMIARÓW
    </button>
</div>
<div id="mStat" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 2000;">
    <div style="background: white; margin: 40px auto; padding: 25px; width: 85%; max-height: 85vh; border-radius: 12px; overflow-y: auto; position: relative;">
        <button onclick="document.getElementById('mStat').style.display='none'" style="position: sticky; top: 0; float: right; padding: 10px; background: #c0392b; color: white; border: none; border-radius: 4px; cursor: pointer;">ZAMKNIJ</button>
        {st_html}
    </div>
</div>
"""))


fg_markers = FeatureGroup(name="Punkty detekcji", show=True)
for i in range(len(coords_df)):
    cid = coords_df.iloc[i]["clean_id"]
    r_id = coords_df.iloc[i]["Nr detektora"]
    
    val_str, clr = "Brak danych", "gray"
    if cid in detector_df.index:
        v = detector_df.loc[cid, "Stężenie radonu"]
        val_str = f"{v:.2f} Bq/m³"
        clr = get_clr(v)
    
    b_type = str(coords_df.iloc[i]["Typ budynku"]).lower().replace("/blok", "")
    
    pop_h = f"""<div style="font-family: Arial; min-width: 180px;">
                <b style="color: #2980b9;">Detektor: {r_id}</b><br>
                <b>Stężenie:</b> {val_str}<br>
                <b>Budynek:</b> {b_type}<br>
                <b>Rok budowy:</b> {coords_df.iloc[i]["Rok Budowy"]}
                </div>"""
    
    folium.Marker(
        location=[coords_df.iloc[i]["Latitude"], coords_df.iloc[i]["Longitude"]],
        popup=folium.Popup(pop_h, max_width=300),
        icon=folium.Icon(color=clr, icon='info-sign'),
        tags=[b_type]
    ).add_to(fg_markers)

fg_markers.add_to(m)
add_triangulation_layer(m, coords_df, detector_df, g_min, g_max)

TagFilterButton(list(coords_df["Typ budynku"].astype(str).str.lower().unique())).add_to(m)
LayerControl(collapsed=False).add_to(m)

f_name = "mapa_radon_final_v2.html"
m.save(f_name)
webbrowser.open(f_name)
