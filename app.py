import io
import time
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Outil de WebFetch", page_icon="🕸️", layout="centered"
)

st.title("🕸️ Outil de WebFetch XPLR")
st.markdown(
    "Uploadez votre fichier CSV ou TSV, paramétrez vos colonnes, et laissez"
    " l'outil aspirer le texte."
)


def nettoyer_texte(html_element):
  if not html_element:
    return ""
  return html_element.get_text(separator="\n", strip=True)


def fetch_url(url, selecteur_css, retries=2):
  headers = {
      "User-Agent": (
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
          " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0"
          " Safari/537.36"
      )
  }
  texte = ""
  statut = ""
  for tentative in range(retries):
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
        break
      elif reponse.status_code == 429:
        statut = "Bloqué (429)"
        time.sleep(2)
      else:
        statut = f"Erreur {reponse.status_code}"
        break
    except Exception:
      statut = "Erreur de connexion"
      time.sleep(1)

  return {"URL_Scrapee": url, "Statut_WebFetch": statut, "Texte_Extrait": texte}


fichier_upload = st.file_uploader(
    "1. Importez votre fichier CSV ou TSV", type=["csv", "tsv"]
)

if fichier_upload is not None:
  separateur = "\t" if fichier_upload.name.endswith(".tsv") else ","
  df = pd.read_csv(fichier_upload, sep=separateur, low_memory=False)
  st.success(f"Fichier chargé avec succès ! ({len(df)} lignes)")

  st.subheader("2. Paramétrage des colonnes")

  colonnes = df.columns.tolist()
  options_avec_aucun = ["(Aucune)"] + colonnes
  
  # Nettoyage des noms de colonnes (minuscules + suppression des espaces invisibles)
  colonnes_propres = [str(c).strip().lower() for c in colonnes]

  # Détection automatique ID / Identifiant (Priorité absolue à "identifiant")
  index_id_defaut = 0
  for var in ["identifiant", "id", "variant_id", "sku", "id_produit", "product_id"]:
    if var in colonnes_propres:
      index_id_defaut = colonnes_propres.index(var) + 1  # +1 pour décaler à cause de "(Aucune)"
      break

  # Détection automatique Titre (Priorité absolue à "titre")
  index_titre_defaut = 0
  for var in ["titre", "title", "nom", "name", "product_name"]:
    if var in colonnes_propres:
      index_titre_defaut = colonnes_propres.index(var) + 1
      break

  # Détection automatique URL (Priorité absolue à "lien")
  index_url_defaut = 0
  for var in ["lien", "url", "link", "product_url"]:
    if var in colonnes_propres:
      index_url_defaut = colonnes_propres.index(var)
      break

  col_id_choix = st.selectbox(
      "Sélectionnez la colonne Identifiant / ID :",
      options_avec_aucun,
      index=index_id_defaut,
  )
  col_titre_choix = st.selectbox(
      "Sélectionnez la colonne Titre du produit :",
      options_avec_aucun,
      index=index_titre_defaut,
  )
  colonne_url = st.selectbox(
      "Sélectionnez la colonne contenant les URLs à aspirer :",
      colonnes,
      index=index_url_defaut,
  )

  selecteur_css = st.text_input(
      "Sélecteur CSS (Optionnel)",
      help="Ex: 'div.description' pour cibler une zone précise.",
  )

  if st.button("🚀 Lancer l'aspiration Web", type="primary"):
    urls_uniques = df[colonne_url].dropna().unique().tolist()
    total = len(urls_uniques)

    st.info(f"Démarrage de l'aspiration rapide pour {total} liens uniques...")
    barre_progression = st.progress(0)
    statut_texte = st.empty()

    resultats = []
    with ThreadPoolExecutor(max_workers=3) as executor:
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

    cols_finales = []
    if col_id_choix != "(Aucune)":
      cols_finales.append(col_id_choix)
    if col_titre_choix != "(Aucune)":
      cols_finales.append(col_titre_choix)

    cols_finales.extend(["Statut_WebFetch", "Texte_Extrait"])
    df_final = df_merged[cols_finales]

    succes = (df_resultats["Statut_WebFetch"].str.startswith("OK")).sum()
    echecs = total - succes

    if echecs == 0:
      st.success(
          f"🎉 Aspiration 100 % réussie ! Les {total} pages ont été récupérées"
          " sans erreur."
      )
    else:
      st.warning(
          f"⚠️ Aspiration terminée : {succes}/{total} pages récupérées avec"
          " succès."
      )

    buffer = io.BytesIO()
    df_final.to_csv(buffer, index=False, encoding="utf-8-sig")

    st.download_button(
        label="📥 Télécharger le fichier final épuré",
        data=buffer.getvalue(),
        file_name="RESULTATS_WebFetch_Epure.csv",
        mime="text/csv",
        type="primary",
    )
