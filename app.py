import io
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Outil de WebFetch", page_icon="🕸️", layout="centered"
)

st.title("🕸️ Outil de WebFetch Universel")
st.markdown(
    "Uploadez votre fichier CSV ou TSV, choisissez la colonne contenant les"
    " liens, et laissez l'outil aspirer le texte des pages web"
    " automatiquement."
)


def nettoyer_texte(html_element):
  if not html_element:
    return ""
  return html_element.get_text(separator="\n", strip=True)


def fetch_url(url, selecteur_css):
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      )
  }
  try:
    reponse = requests.get(url, headers=headers, timeout=8)
    if reponse.status_code == 200:
      soup = BeautifulSoup(reponse.text, "html.parser")
      if selecteur_css:
        zone = soup.select_one(selecteur_css)
        texte = nettoyer_texte(zone) if zone else ""
        statut = "OK" if zone else "Zone introuvable"
      else:
        texte = nettoyer_texte(soup.body) if soup.body else ""
        statut = "OK (Page entière)"
    elif reponse.status_code == 429:
      statut = "Bloqué (429)"
    else:
      statut = f"Erreur {reponse.status_code}"
  except Exception:
    statut = "Erreur de connexion"
  return {"URL_Scrapee": url, "Statut_WebFetch": statut, "Texte_Extrait": texte}


fichier_upload = st.file_uploader(
    "1. Importez votre fichier CSV ou TSV", type=["csv", "tsv"]
)

if fichier_upload is not None:
  separateur = "\t" if fichier_upload.name.endswith(".tsv") else ","
  df = pd.read_csv(fichier_upload, sep=separateur, low_memory=False)
  st.success(f"Fichier chargé avec succès ! ({len(df)} lignes)")

  st.subheader("2. Paramétrage")

  colonnes = df.columns.tolist()

  # Détection automatique de la colonne URL par défaut
  index_defaut = 0
  variantes_liens = ["lien", "url", "link", "Lien", "URL", "Link", "product_url"]
  for variante in variantes_liens:
    if variante in colonnes:
      index_defaut = colonnes.index(variante)
      break

  colonne_url = st.selectbox(
      "Quelle colonne contient les URLs à aspirer ?",
      colonnes,
      index=index_defaut,
  )
  selecteur_css = st.text_input(
      "Sélecteur CSS (Optionnel)",
      help="Ex: 'div.description' pour cibler une zone précise.",
  )

  if st.button("🚀 Lancer l'aspiration Web", type="primary"):
    urls_uniques = df[colonne_url].dropna().unique().tolist()
    total = len(urls_uniques)

    st.info(
        f"Démarrage de l'aspiration accélérée pour {total} liens uniques..."
    )
    barre_progression = st.progress(0)
    statut_texte = st.empty()

    resultats = []
    with ThreadPoolExecutor(max_workers=5) as executor:
      futures = [
          executor.submit(fetch_url, url, selecteur_css)
          for url in urls_uniques
      ]
      for i, future in enumerate(futures):
        res = future.result()
        resultats.append(res)
        barre_progression.progress((i + 1) / total)
        statut_texte.text(f"Progression : {i + 1}/{total} URLs traitées")

    df_resultats = pd.DataFrame(resultats)
    df_merged = df.merge(
        df_resultats, left_on=colonne_url, right_on="URL_Scrapee", how="left"
    )

    # Détection et conservation uniquement des colonnes identifiantes essentielles
    cols_a_garder = []

    # ID
    col_id = next(
        (
            c
            for c in colonnes
            if c.lower()
            in ["id", "variant_id", "sku", "id_produit", "product_id"]
        ),
        None,
    )
    if col_id:
      cols_a_garder.append(col_id)

    # Titre
    col_titre = next(
        (
            c
            for c in colonnes
            if c.lower() in ["titre", "title", "nom", "name", "product_name"]
        ),
        None,
    )
    if col_titre and col_titre not in cols_a_garder:
      cols_a_garder.append(col_titre)

    # URL
    if colonne_url not in cols_a_garder:
      cols_a_garder.append(colonne_url)

    # Si aucune colonne d'ID ou de Titre n'a été reconnue, on conserve les 2 premières colonnes
    if len(cols_a_garder) == 1 and cols_a_garder[0] == colonne_url:
      cols_a_garder = colonnes[:2]

    cols_finales = cols_a_garder + ["Statut_WebFetch", "Texte_Extrait"]
    cols_finales = [c for c in cols_finales if c in df_merged.columns]

    df_final = df_merged[cols_finales]

    succes = (df_resultats["Statut_WebFetch"].str.startswith("OK")).sum()
    echecs = total - succes

    if echecs == 0:
      st.success(
          f"🎉 Aspiration 100 % réussie ! Les {total} pages ont été récupérées"
          " sans aucune erreur."
      )
    else:
      st.warning(
          f"⚠️ Aspiration incomplète : {succes}/{total} pages récupérées avec"
          f" succès ({echecs} échec(s) à vérifier dans la colonne"
          " 'Statut_WebFetch')."
      )

    buffer = io.BytesIO()
    df_final.to_csv(buffer, index=False, encoding="utf-8-sig")

    st.download_button(
        label="📥 Télécharger le fichier final allégé",
        data=buffer.getvalue(),
        file_name="RESULTATS_WebFetch_Allege.csv",
        mime="text/csv",
        type="primary",
    )
