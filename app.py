import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import io

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Outil de WebFetch", page_icon="🕸️", layout="centered")

st.title("🕸️ Outil de WebFetch Universel")
st.markdown("Uploadez votre fichier CSV, choisissez la colonne contenant les liens, et laissez l'outil aspirer le texte des pages web automatiquement.")

def nettoyer_texte(html_element):
    if not html_element: return ""
    return html_element.get_text(separator='\n', strip=True)

# --- ÉTAPE 1 : UPLOAD DU FICHIER ---
fichier_upload = st.file_uploader("1. Importez votre fichier CSV ou TSV", type=['csv', 'tsv'])

if fichier_upload is not None:
    # Lecture du fichier
    separateur = '\t' if fichier_upload.name.endswith('.tsv') else ','
    df = pd.read_csv(fichier_upload, sep=separateur, low_memory=False)
    
    st.success(f"Fichier chargé avec succès ! ({len(df)} lignes)")
    
    # --- ÉTAPE 2 : PARAMÉTRAGE ---
    st.subheader("2. Paramétrage")
    colonne_url = st.selectbox("Quelle colonne contient les URLs à aspirer ?", df.columns)
    
    selecteur_css = st.text_input("Sélecteur CSS (Optionnel)", help="Ex: 'div.description' pour cibler une zone précise. Laissez vide pour aspirer toute la page.")
    
    # --- ÉTAPE 3 : LANCEMENT ---
    if st.button("🚀 Lancer l'aspiration Web", type="primary"):
        urls_uniques = df[colonne_url].dropna().unique()
        
        st.info(f"Démarrage de l'aspiration pour {len(urls_uniques)} liens uniques...")
        barre_progression = st.progress(0)
        statut_texte = st.empty()
        
        resultats = []
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        
        for i, url in enumerate(urls_uniques):
            statut_texte.text(f"Aspiration en cours : {url}")
            texte_extrait = ""
            statut = "En attente"
            
            try:
                reponse = requests.get(url, headers=headers, timeout=10)
                if reponse.status_code == 200:
                    soup = BeautifulSoup(reponse.text, 'html.parser')
                    if selecteur_css:
                        zone = soup.select_one(selecteur_css)
                        texte_extrait = nettoyer_texte(zone) if zone else ""
                        statut = "OK" if zone else "Zone introuvable"
                    else:
                        texte_extrait = nettoyer_texte(soup.body) if soup.body else ""
                        statut = "OK (Page entière)"
                elif reponse.status_code == 429:
                    statut = "Bloqué (429)"
                    time.sleep(5) # Pause en cas de blocage
                else:
                    statut = f"Erreur {reponse.status_code}"
            except Exception as e:
                statut = "Erreur de connexion"
                
            resultats.append({'URL_Scrapee': url, 'Statut_WebFetch': statut, 'Texte_Extrait': texte_extrait})
            
            # Mise à jour de la barre de progression
            barre_progression.progress((i + 1) / len(urls_uniques))
            time.sleep(1) # Pause polie entre chaque requête
            
        statut_texte.success("Aspiration terminée avec succès !")
        
        # --- ÉTAPE 4 : TÉLÉCHARGEMENT ---
        df_resultats = pd.DataFrame(resultats)
        df_final = df.merge(df_resultats, left_on=colonne_url, right_on='URL_Scrapee', how='left')
        
        # Convertir en CSV pour le téléchargement
        buffer = io.BytesIO()
        df_final.to_csv(buffer, index=False, encoding='utf-8-sig')
        
        st.download_button(
            label="📥 Télécharger le fichier final enrichi",
            data=buffer.getvalue(),
            file_name="RESULTATS_WebFetch.csv",
            mime="text/csv",
            type="primary"
        )