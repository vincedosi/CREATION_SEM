"""
🛡️ Architecte d'Autorité Sémantique v8.2
=========================================
BASÉ SUR v8.1 + AUTO-FILIATION (Parent Organization P749)

Quand tu sélectionnes une entité Wikidata, la Filiation (Parent Organization)
est automatiquement récupérée via la propriété P749.

Ex: Boursorama → Société Générale (Q270618)
    BNP Paribas Suisse → BNP Paribas (Q499707)
"""

import streamlit as st
import requests
import json
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from datetime import datetime

# ============================================================================
# VERSION
# ============================================================================
VERSION = "8.2.0"
BUILD_DATE = "2025-01-19"
BUILD_ID = "BUILD-820-FILIATION"

# ============================================================================
# CONFIG
# ============================================================================
st.set_page_config(
    page_title=f"AAS v{VERSION}",
    page_icon="🛡️",
    layout="wide"
)

# Bandeau version
st.markdown(f"""
<div style="
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
    font-weight: bold;
">
    🛡️ Architecte d'Autorité Sémantique v{VERSION} | {BUILD_ID}
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE
# ============================================================================
defaults = {
    'logs': [],
    'entity': None,
    'wiki_results': [],
    'insee_results': [],
    'social_links': {k: '' for k in ['linkedin', 'twitter', 'facebook', 'instagram', 'youtube']},
    'authenticated': False,
    'mistral_key': ''
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "OK": "✅", "ERROR": "❌", "WARN": "⚠️", "HTTP": "🌐"}
    st.session_state.logs.append(f"{icons.get(level, '•')} [{ts}] {msg}")
    if len(st.session_state.logs) > 50:
        st.session_state.logs = st.session_state.logs[-50:]


# ============================================================================
# DATA CLASS
# ============================================================================
@dataclass
class Entity:
    # Identité
    name: str = ""
    name_en: str = ""
    legal_name: str = ""
    description_fr: str = ""
    description_en: str = ""
    expertise_fr: str = ""
    expertise_en: str = ""
    
    # Identifiants
    qid: str = ""
    siren: str = ""
    siret: str = ""
    lei: str = ""
    naf: str = ""
    website: str = ""
    
    # Type
    org_type: str = "Organization"
    
    # Filiation (Parent Organization - P749)
    parent_org_name: str = ""
    parent_org_qid: str = ""
    parent_org_siren: str = ""
    
    # Adresse
    address: str = ""

    def score(self) -> int:
        s = 0
        if self.qid: s += 20
        if self.siren: s += 20
        if self.lei: s += 15
        if self.website: s += 15
        if self.parent_org_qid: s += 15  # Bonus filiation!
        if self.expertise_fr: s += 15
        return min(s, 100)


if st.session_state.entity is None:
    st.session_state.entity = Entity()


# ============================================================================
# WIKIDATA API
# ============================================================================
class WikidataAPI:
    """API Wikidata avec récupération automatique du Parent (P749)."""
    
    BASE_URL = "https://www.wikidata.org/w/api.php"
    HEADERS = {
        "User-Agent": f"AAS-Bot/{VERSION} (Streamlit; contact@example.com)",
        "Accept": "application/json"
    }
    
    @staticmethod
    def search(query: str) -> List[Dict]:
        """Recherche d'entités."""
        log(f"Wikidata search: '{query}'", "HTTP")
        
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "fr",
            "uselang": "fr",
            "format": "json",
            "limit": 12,
            "type": "item"
        }
        
        try:
            r = requests.get(WikidataAPI.BASE_URL, params=params, headers=WikidataAPI.HEADERS, timeout=20)
            log(f"HTTP {r.status_code}", "HTTP")
            
            if r.status_code == 200:
                data = r.json()
                results = data.get('search', [])
                log(f"{len(results)} résultats", "OK")
                return [{
                    'qid': item['id'],
                    'label': item.get('label', item['id']),
                    'desc': item.get('description', '')
                } for item in results]
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
        
        return []
    
    @staticmethod
    def get_entity(qid: str) -> Dict:
        """
        Récupère les détails d'une entité AVEC le Parent Organization (P749).
        C'est ici que la magie de la Filiation opère!
        """
        log(f"Get entity: {qid}", "HTTP")
        
        result = {
            "name_fr": "", "name_en": "", 
            "desc_fr": "", "desc_en": "",
            "siren": "", "lei": "", "website": "",
            "parent_qid": "", "parent_name": ""
        }
        
        params = {
            "action": "wbgetentities",
            "ids": qid,
            "languages": "fr|en",
            "props": "labels|descriptions|claims",
            "format": "json"
        }
        
        try:
            r = requests.get(WikidataAPI.BASE_URL, params=params, headers=WikidataAPI.HEADERS, timeout=20)
            
            if r.status_code == 200:
                data = r.json()
                entity = data.get('entities', {}).get(qid, {})
                
                if not entity:
                    log(f"Entité {qid} non trouvée", "ERROR")
                    return result
                
                # Labels
                labels = entity.get('labels', {})
                result["name_fr"] = labels.get('fr', {}).get('value', '')
                result["name_en"] = labels.get('en', {}).get('value', '')
                
                # Descriptions
                descs = entity.get('descriptions', {})
                result["desc_fr"] = descs.get('fr', {}).get('value', '')
                result["desc_en"] = descs.get('en', {}).get('value', '')
                
                # Claims (propriétés)
                claims = entity.get('claims', {})
                
                # P1616 = SIREN
                if 'P1616' in claims:
                    try:
                        result["siren"] = claims['P1616'][0]['mainsnak']['datavalue']['value']
                        log(f"SIREN: {result['siren']}", "OK")
                    except:
                        pass
                
                # P1278 = LEI
                if 'P1278' in claims:
                    try:
                        result["lei"] = claims['P1278'][0]['mainsnak']['datavalue']['value']
                        log(f"LEI: {result['lei']}", "OK")
                    except:
                        pass
                
                # P856 = Website
                if 'P856' in claims:
                    try:
                        result["website"] = claims['P856'][0]['mainsnak']['datavalue']['value']
                        log(f"Website: {result['website']}", "OK")
                    except:
                        pass
                
                # ⭐ P749 = PARENT ORGANIZATION (FILIATION) ⭐
                if 'P749' in claims:
                    try:
                        parent_value = claims['P749'][0]['mainsnak']['datavalue']['value']
                        
                        # Le parent est un objet avec 'id'
                        if isinstance(parent_value, dict):
                            result["parent_qid"] = parent_value.get('id', '')
                        elif isinstance(parent_value, str):
                            result["parent_qid"] = parent_value
                        
                        if result["parent_qid"]:
                            log(f"🔗 Parent trouvé: {result['parent_qid']}", "OK")
                            
                            # Récupérer le nom du parent
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            log(f"🔗 Parent: {result['parent_name']} ({result['parent_qid']})", "OK")
                    except Exception as e:
                        log(f"Erreur P749: {e}", "WARN")
                else:
                    log("Pas de Parent Organization (P749)", "INFO")
                
                log(f"Entity chargée: {result['name_fr']}", "OK")
                
        except Exception as e:
            log(f"Exception: {e}", "ERROR")
        
        return result
    
    @staticmethod
    def get_label(qid: str) -> str:
        """Récupère le label d'un QID (pour le parent)."""
        try:
            params = {
                "action": "wbgetentities",
                "ids": qid,
                "languages": "fr|en",
                "props": "labels",
                "format": "json"
            }
            r = requests.get(WikidataAPI.BASE_URL, params=params, headers=WikidataAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                labels = r.json().get('entities', {}).get(qid, {}).get('labels', {})
                return labels.get('fr', {}).get('value', '') or labels.get('en', {}).get('value', qid)
        except:
            pass
        return qid


# ============================================================================
# INSEE API
# ============================================================================
class INSEEAPI:
    """API INSEE gratuite."""
    
    @staticmethod
    def search(query: str) -> List[Dict]:
        log(f"INSEE search: '{query}'", "HTTP")
        
        try:
            r = requests.get(
                "https://recherche-entreprises.api.gouv.fr/search",
                params={"q": query, "per_page": 10},
                timeout=15
            )
            
            if r.status_code == 200:
                results = r.json().get('results', [])
                log(f"INSEE: {len(results)} résultats", "OK")
                
                return [{
                    'siren': item.get('siren', ''),
                    'siret': item.get('siege', {}).get('siret', ''),
                    'name': item.get('nom_complet', ''),
                    'legal_name': item.get('nom_raison_sociale', ''),
                    'naf': item.get('activite_principale', ''),
                    'address': f"{item.get('siege', {}).get('adresse', '')} {item.get('siege', {}).get('code_postal', '')} {item.get('siege', {}).get('commune', '')}",
                    'active': item.get('etat_administratif') == 'A'
                } for item in results]
        except Exception as e:
            log(f"INSEE error: {e}", "ERROR")
        
        return []


# ============================================================================
# MISTRAL API
# ============================================================================
def mistral_optimize(api_key: str, entity: Entity) -> Optional[Dict]:
    """Enrichissement Mistral (fallback si pas de parent Wikidata)."""
    if not api_key:
        return None
    
    log("Mistral optimization...", "HTTP")
    
    prompt = f"""Expert SEO. Analyse cette entreprise française:
NOM: {entity.name}
SIREN: {entity.siren or 'N/A'}
QID: {entity.qid or 'N/A'}

Génère en JSON:
- description_fr: Description SEO (150-200 car)
- description_en: English translation  
- expertise_fr: 3-5 domaines (virgules)
- expertise_en: English translation
- parent_org_name: Maison mère (null si indépendant/inconnu)
- parent_org_qid: QID Wikidata du parent (Qxxxxx ou null)

RÉPONDS UNIQUEMENT EN JSON VALIDE:"""

    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.2
            },
            timeout=30
        )
        
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            result = json.loads(content)
            log("Mistral OK", "OK")
            return result
        else:
            log(f"Mistral HTTP {r.status_code}", "ERROR")
    except Exception as e:
        log(f"Mistral error: {e}", "ERROR")
    
    return None


# ============================================================================
# AUTH
# ============================================================================
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align:center'>🔐 Accès Restreint</h2>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pwd = st.text_input("Mot de passe:", type="password")
        if st.button("🔓 Déverrouiller", type="primary", use_container_width=True):
            if pwd == "SEOTOOLS":
                st.session_state.authenticated = True
                log("Auth OK", "OK")
                st.rerun()
            else:
                st.error("❌ Incorrect")
    st.stop()


# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Logs
    with st.expander("📟 Logs", expanded=True):
        log_box = st.container(height=200)
        with log_box:
            for entry in reversed(st.session_state.logs[-15:]):
                if "ERROR" in entry:
                    st.error(entry)
                elif "OK" in entry:
                    st.success(entry)
                else:
                    st.caption(entry)
    
    st.divider()
    
    # Mistral Key
    st.session_state.mistral_key = st.text_input("🔑 Clé Mistral", st.session_state.mistral_key, type="password")
    
    st.divider()
    
    # Recherche
    st.subheader("🔍 Recherche")
    source = st.radio("Source", ["Wikidata", "INSEE", "Les deux"], horizontal=True)
    query = st.text_input("Organisation", placeholder="Boursorama, IKEA...")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔎 Chercher", type="primary", use_container_width=True):
            if query:
                if source in ["Wikidata", "Les deux"]:
                    st.session_state.wiki_results = WikidataAPI.search(query)
                if source in ["INSEE", "Les deux"]:
                    st.session_state.insee_results = INSEEAPI.search(query)
                st.rerun()
    with c2:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state.entity = Entity()
            st.session_state.wiki_results = []
            st.session_state.insee_results = []
            st.rerun()
    
    # Résultats Wikidata
    if st.session_state.wiki_results:
        st.markdown("**🌐 Wikidata:**")
        for i, item in enumerate(st.session_state.wiki_results[:8]):
            label = f"{item['qid']}: {item['label'][:22]}"
            if st.button(label, key=f"w{i}", use_container_width=True):
                log(f"Selection: {item['qid']}", "INFO")
                
                # ⭐ Récupération avec FILIATION automatique ⭐
                details = WikidataAPI.get_entity(item['qid'])
                
                e = st.session_state.entity
                e.qid = item['qid']
                e.name = details['name_fr'] or item['label']
                e.name_en = details['name_en']
                e.description_fr = details['desc_fr']
                e.description_en = details['desc_en']
                e.siren = e.siren or details['siren']
                e.lei = details['lei']
                e.website = e.website or details['website']
                
                # ⭐ FILIATION AUTO ⭐
                if details['parent_qid']:
                    e.parent_org_qid = details['parent_qid']
                    e.parent_org_name = details['parent_name']
                
                st.rerun()
    
    # Résultats INSEE
    if st.session_state.insee_results:
        st.markdown("**🏛️ INSEE:**")
        for i, item in enumerate(st.session_state.insee_results[:6]):
            status = "🟢" if item['active'] else "🔴"
            if st.button(f"{status} {item['name'][:22]}", key=f"i{i}", use_container_width=True):
                e = st.session_state.entity
                e.name = e.name or item['name']
                e.legal_name = item['legal_name']
                e.siren = item['siren']
                e.siret = item['siret']
                e.naf = item['naf']
                e.address = item['address']
                log(f"INSEE: {item['name']}", "OK")
                st.rerun()


# ============================================================================
# MAIN CONTENT
# ============================================================================
e = st.session_state.entity

if e.name or e.qid or e.siren:
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Score", f"{e.score()}%")
    col2.metric("QID", e.qid or "—")
    col3.metric("SIREN", e.siren or "—")
    
    # ⭐ Affichage Parent avec lien ⭐
    if e.parent_org_qid:
        col4.metric("🔗 Parent", e.parent_org_qid)
    else:
        col4.metric("Parent", "—")
    
    # Tabs
    tabs = st.tabs(["🆔 Identité", "🔗 Filiation", "🪄 GEO Magic", "📱 Social", "💾 JSON-LD"])
    
    # Tab Identité
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            e.org_type = st.selectbox("Type Schema.org", ["Organization", "Corporation", "LocalBusiness", "BankOrCreditUnion", "InsuranceAgency"])
            e.name = st.text_input("Nom", e.name)
            e.legal_name = st.text_input("Raison sociale", e.legal_name)
            e.siren = st.text_input("SIREN", e.siren)
            e.siret = st.text_input("SIRET", e.siret)
        with c2:
            e.qid = st.text_input("QID Wikidata", e.qid)
            e.lei = st.text_input("LEI", e.lei)
            e.naf = st.text_input("NAF", e.naf)
            e.website = st.text_input("Site web", e.website)
            e.address = st.text_input("Adresse", e.address)
    
    # ⭐ Tab Filiation ⭐
    with tabs[1]:
        st.subheader("🔗 Filiation (Parent Organization)")
        
        st.info("💡 La filiation est **automatiquement récupérée** depuis Wikidata (propriété P749) quand tu sélectionnes une entité.")
        
        c1, c2 = st.columns(2)
        with c1:
            e.parent_org_name = st.text_input("Nom de la maison mère", e.parent_org_name)
        with c2:
            e.parent_org_qid = st.text_input("QID Wikidata maison mère", e.parent_org_qid)
        
        e.parent_org_siren = st.text_input("SIREN maison mère (optionnel)", e.parent_org_siren)
        
        if e.parent_org_qid:
            st.success(f"✅ **Filiation établie:** {e.name} → [{e.parent_org_name}](https://www.wikidata.org/wiki/{e.parent_org_qid})")
        elif e.name:
            st.warning("⚠️ Pas de filiation trouvée dans Wikidata. Tu peux utiliser **GEO Magic** pour la détecter via Mistral.")
    
    # Tab GEO Magic
    with tabs[2]:
        st.subheader("🪄 GEO Magic (Mistral AI)")
        
        st.info("Utilise Mistral AI pour générer les descriptions SEO et détecter la filiation si elle n'est pas dans Wikidata.")
        
        if st.button("🪄 Auto-Optimize", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Mistral en cours..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                
                if result:
                    e.description_fr = result.get('description_fr', e.description_fr)
                    e.description_en = result.get('description_en', e.description_en)
                    e.expertise_fr = result.get('expertise_fr', e.expertise_fr)
                    e.expertise_en = result.get('expertise_en', e.expertise_en)
                    
                    # Filiation Mistral (si pas déjà remplie)
                    if not e.parent_org_name and result.get('parent_org_name'):
                        e.parent_org_name = result['parent_org_name']
                        log(f"Parent Mistral: {e.parent_org_name}", "OK")
                    if not e.parent_org_qid and result.get('parent_org_qid'):
                        e.parent_org_qid = result['parent_org_qid']
                    
                    st.rerun()
            else:
                st.error("🔑 Clé Mistral requise (sidebar)")
        
        e.description_fr = st.text_area("Description FR", e.description_fr, height=100)
        e.description_en = st.text_area("Description EN", e.description_en, height=100)
        
        c1, c2 = st.columns(2)
        with c1:
            e.expertise_fr = st.text_input("Expertise FR", e.expertise_fr)
        with c2:
            e.expertise_en = st.text_input("Expertise EN", e.expertise_en)
    
    # Tab Social
    with tabs[3]:
        st.subheader("📱 Réseaux sociaux (sameAs)")
        social = st.session_state.social_links
        
        c1, c2 = st.columns(2)
        with c1:
            social['linkedin'] = st.text_input("LinkedIn", social['linkedin'])
            social['twitter'] = st.text_input("Twitter/X", social['twitter'])
            social['facebook'] = st.text_input("Facebook", social['facebook'])
        with c2:
            social['instagram'] = st.text_input("Instagram", social['instagram'])
            social['youtube'] = st.text_input("YouTube", social['youtube'])
    
    # Tab JSON-LD
    with tabs[4]:
        st.subheader("💾 Export JSON-LD")
        
        # Build sameAs
        same_as = []
        if e.qid:
            same_as.append(f"https://www.wikidata.org/wiki/{e.qid}")
        same_as.extend([v for v in st.session_state.social_links.values() if v])
        
        # Build identifiers
        identifiers = []
        if e.siren:
            identifiers.append({"@type": "PropertyValue", "propertyID": "SIREN", "value": e.siren})
        if e.lei:
            identifiers.append({"@type": "PropertyValue", "propertyID": "LEI", "value": e.lei})
        
        # Build parent organization
        parent = None
        if e.parent_org_name:
            parent = {"@type": "Organization", "name": e.parent_org_name}
            if e.parent_org_qid:
                parent["sameAs"] = f"https://www.wikidata.org/wiki/{e.parent_org_qid}"
        
        # Build JSON-LD
        json_ld = {
            "@context": "https://schema.org",
            "@type": e.org_type,
            "name": e.name
        }
        
        if e.legal_name:
            json_ld["legalName"] = e.legal_name
        if e.website:
            json_ld["@id"] = f"{e.website.rstrip('/')}/#organization"
            json_ld["url"] = e.website
        if e.description_fr:
            json_ld["description"] = e.description_fr
        if e.siren:
            json_ld["taxID"] = f"FR{e.siren}"
        if identifiers:
            json_ld["identifier"] = identifiers
        if same_as:
            json_ld["sameAs"] = same_as
        if e.address:
            json_ld["address"] = {"@type": "PostalAddress", "streetAddress": e.address}
        if parent:
            json_ld["parentOrganization"] = parent
        if e.expertise_fr:
            json_ld["knowsAbout"] = [x.strip() for x in e.expertise_fr.split(',')]
        
        st.json(json_ld)
        
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📄 Télécharger JSON-LD",
                json.dumps(json_ld, indent=2, ensure_ascii=False),
                f"jsonld_{e.siren or e.qid or 'export'}.json",
                mime="application/json"
            )
        with c2:
            config = {"entity": asdict(e), "social_links": st.session_state.social_links}
            st.download_button(
                "💾 Sauvegarder Config",
                json.dumps(config, indent=2, ensure_ascii=False),
                f"config_{e.siren or e.qid or 'export'}.json"
            )

else:
    st.info("👈 Recherche une organisation dans la sidebar pour commencer")
    
    st.markdown(f"""
    ### 🆕 Nouveautés v{VERSION}
    
    - **🔗 Filiation automatique** : Quand tu sélectionnes une entité Wikidata, le Parent Organization (P749) est automatiquement récupéré
    - **Exemple** : Cherche "Boursorama" → Sélectionne Q2110465 → La filiation "Société Générale" apparaît automatiquement!
    
    ### 📋 Workflow
    
    1. **Recherche** une organisation (Wikidata ou INSEE)
    2. **Sélectionne** le bon résultat
    3. La **Filiation** se remplit automatiquement si elle existe dans Wikidata
    4. Utilise **GEO Magic** pour enrichir avec Mistral
    5. **Exporte** le JSON-LD
    """)

# Footer
st.divider()
st.caption(f"🛡️ AAS v{VERSION} | {BUILD_ID} | {BUILD_DATE}")
