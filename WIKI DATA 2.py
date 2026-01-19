"""
🛡️ Architecte d'Autorité Sémantique v8.3
=========================================
FILIATION AMÉLIORÉE:
- P749 (parent organization) 
- P127 (owned by) - fallback si P749 absent
- P355 inverse (subsidiary) 
- Mistral AI avec prompt optimisé pour trouver le parent

Ex: Boursorama → Société Générale (via P127 ou Mistral)
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
VERSION = "8.3.0"
BUILD_DATE = "2025-01-19"
BUILD_ID = "BUILD-830-FILIATION-ENHANCED"

# ============================================================================
# CONFIG
# ============================================================================
st.set_page_config(page_title=f"AAS v{VERSION}", page_icon="🛡️", layout="wide")

# Bandeau version
st.markdown(f"""
<div style="
    background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%);
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    margin-bottom: 20px;
    text-align: center;
    font-weight: bold;
">
    🛡️ AAS v{VERSION} | {BUILD_ID} | Filiation Enhanced (P749 + P127 + Mistral)
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
    icons = {"INFO": "ℹ️", "OK": "✅", "ERROR": "❌", "WARN": "⚠️", "HTTP": "🌐", "PARENT": "🔗"}
    st.session_state.logs.append(f"{icons.get(level, '•')} [{ts}] {msg}")
    if len(st.session_state.logs) > 50:
        st.session_state.logs = st.session_state.logs[-50:]


# ============================================================================
# DATA CLASS
# ============================================================================
@dataclass
class Entity:
    name: str = ""
    name_en: str = ""
    legal_name: str = ""
    description_fr: str = ""
    description_en: str = ""
    expertise_fr: str = ""
    expertise_en: str = ""
    qid: str = ""
    siren: str = ""
    siret: str = ""
    lei: str = ""
    naf: str = ""
    website: str = ""
    org_type: str = "Organization"
    parent_org_name: str = ""
    parent_org_qid: str = ""
    parent_org_siren: str = ""
    parent_source: str = ""  # "P749", "P127", "Mistral"
    address: str = ""

    def score(self) -> int:
        s = 0
        if self.qid: s += 20
        if self.siren: s += 20
        if self.lei: s += 15
        if self.website: s += 15
        if self.parent_org_qid: s += 15
        if self.expertise_fr: s += 15
        return min(s, 100)


if st.session_state.entity is None:
    st.session_state.entity = Entity()


# ============================================================================
# WIKIDATA API - FILIATION ENHANCED
# ============================================================================
class WikidataAPI:
    """API Wikidata avec recherche de filiation multi-propriétés."""
    
    BASE_URL = "https://www.wikidata.org/w/api.php"
    HEADERS = {"User-Agent": f"AAS-Bot/{VERSION}", "Accept": "application/json"}
    
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
            if r.status_code == 200:
                results = r.json().get('search', [])
                log(f"{len(results)} résultats", "OK")
                return [{'qid': item['id'], 'label': item.get('label', item['id']), 'desc': item.get('description', '')} for item in results]
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
        return []
    
    @staticmethod
    def get_entity(qid: str) -> Dict:
        """
        Récupère les détails avec FILIATION MULTI-SOURCES:
        1. P749 (parent organization) - priorité 1
        2. P127 (owned by) - priorité 2
        3. Recherche inverse via P355 (subsidiary)
        """
        log(f"Get entity: {qid}", "HTTP")
        
        result = {
            "name_fr": "", "name_en": "", "desc_fr": "", "desc_en": "",
            "siren": "", "lei": "", "website": "",
            "parent_qid": "", "parent_name": "", "parent_source": ""
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
                entity = r.json().get('entities', {}).get(qid, {})
                
                if not entity:
                    return result
                
                # Labels & Descriptions
                labels = entity.get('labels', {})
                descs = entity.get('descriptions', {})
                result["name_fr"] = labels.get('fr', {}).get('value', '')
                result["name_en"] = labels.get('en', {}).get('value', '')
                result["desc_fr"] = descs.get('fr', {}).get('value', '')
                result["desc_en"] = descs.get('en', {}).get('value', '')
                
                claims = entity.get('claims', {})
                log(f"Claims: {len(claims)} propriétés", "INFO")
                
                # SIREN P1616
                if 'P1616' in claims:
                    try:
                        result["siren"] = claims['P1616'][0]['mainsnak']['datavalue']['value']
                        log(f"SIREN: {result['siren']}", "OK")
                    except: pass
                
                # LEI P1278
                if 'P1278' in claims:
                    try:
                        result["lei"] = claims['P1278'][0]['mainsnak']['datavalue']['value']
                    except: pass
                
                # Website P856
                if 'P856' in claims:
                    try:
                        result["website"] = claims['P856'][0]['mainsnak']['datavalue']['value']
                    except: pass
                
                # ========== FILIATION ==========
                
                # 1. P749 - Parent Organization (priorité 1)
                if 'P749' in claims:
                    log("Checking P749 (parent organization)...", "PARENT")
                    try:
                        pval = claims['P749'][0]['mainsnak']['datavalue']['value']
                        if isinstance(pval, dict):
                            result["parent_qid"] = pval.get('id', '')
                        elif isinstance(pval, str):
                            result["parent_qid"] = pval
                        
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P749"
                            log(f"✅ Parent P749: {result['parent_name']} ({result['parent_qid']})", "OK")
                    except Exception as e:
                        log(f"P749 error: {e}", "WARN")
                
                # 2. P127 - Owned By (priorité 2, si P749 vide)
                if not result["parent_qid"] and 'P127' in claims:
                    log("P749 vide, checking P127 (owned by)...", "PARENT")
                    try:
                        pval = claims['P127'][0]['mainsnak']['datavalue']['value']
                        if isinstance(pval, dict):
                            result["parent_qid"] = pval.get('id', '')
                        elif isinstance(pval, str):
                            result["parent_qid"] = pval
                        
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P127"
                            log(f"✅ Parent P127: {result['parent_name']} ({result['parent_qid']})", "OK")
                    except Exception as e:
                        log(f"P127 error: {e}", "WARN")
                
                # 3. Si toujours rien, on log
                if not result["parent_qid"]:
                    log("❌ Pas de P749 ni P127 dans Wikidata", "WARN")
                    log("→ Utilise GEO Magic (Mistral) pour détecter le parent", "INFO")
                
                log(f"Entity chargée: {result['name_fr']}", "OK")
                
        except Exception as e:
            log(f"Exception: {e}", "ERROR")
        
        return result
    
    @staticmethod
    def get_label(qid: str) -> str:
        """Récupère le label d'un QID."""
        try:
            params = {"action": "wbgetentities", "ids": qid, "languages": "fr|en", "props": "labels", "format": "json"}
            r = requests.get(WikidataAPI.BASE_URL, params=params, headers=WikidataAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                labels = r.json().get('entities', {}).get(qid, {}).get('labels', {})
                return labels.get('fr', {}).get('value', '') or labels.get('en', {}).get('value', qid)
        except: pass
        return qid
    
    @staticmethod
    def search_parent_qid(parent_name: str) -> str:
        """Recherche le QID d'un parent par son nom."""
        log(f"Recherche QID pour: {parent_name}", "HTTP")
        try:
            results = WikidataAPI.search(parent_name)
            if results:
                # Prendre le premier résultat
                qid = results[0]['qid']
                log(f"QID trouvé: {qid}", "OK")
                return qid
        except: pass
        return ""


# ============================================================================
# INSEE API
# ============================================================================
class INSEEAPI:
    @staticmethod
    def search(query: str) -> List[Dict]:
        log(f"INSEE search: '{query}'", "HTTP")
        try:
            r = requests.get("https://recherche-entreprises.api.gouv.fr/search", params={"q": query, "per_page": 10}, timeout=15)
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
# MISTRAL API - PROMPT OPTIMISÉ POUR FILIATION
# ============================================================================
def mistral_optimize(api_key: str, entity) -> Optional[Dict]:
    """Mistral avec prompt optimisé pour trouver le parent."""
    if not api_key:
        return None
    
    log("🤖 Mistral: recherche filiation...", "HTTP")
    
    # Prompt spécialement conçu pour trouver le parent
    prompt = f"""Tu es un expert en analyse d'entreprises et données Wikidata.

ENTREPRISE À ANALYSER:
- Nom: {entity.name}
- SIREN: {entity.siren or 'Non renseigné'}
- QID Wikidata: {entity.qid or 'Non renseigné'}
- Site web: {entity.website or 'Non renseigné'}

MISSION PRIORITAIRE - FILIATION:
1. Identifie la MAISON MÈRE / SOCIÉTÉ MÈRE / HOLDING de cette entreprise
2. Pour les banques en ligne françaises, vérifie si c'est une filiale d'un grand groupe bancaire
3. Exemples connus:
   - Boursorama / BoursoBank → Société Générale (Q270618)
   - Hello Bank → BNP Paribas (Q499707)
   - Fortuneo → Crédit Mutuel Arkéa (Q3006220)
   - Orange Bank → Orange (Q1431486)

RÉPONDS EN JSON STRICT (pas de markdown, pas de commentaires):
{{
    "description_fr": "Description SEO optimisée 150-200 caractères",
    "description_en": "English SEO description",
    "expertise_fr": "Domaine1, Domaine2, Domaine3",
    "expertise_en": "Domain1, Domain2, Domain3",
    "parent_org_name": "NOM EXACT de la maison mère (ou null si indépendante)",
    "parent_org_qid": "QID Wikidata du parent ex: Q270618 (ou null si inconnu)"
}}

IMPORTANT: 
- Pour Boursorama/BoursoBank, le parent est Société Générale (Q270618)
- Sois précis sur le QID, vérifie dans ta base de connaissances
- Si tu n'es pas sûr du QID, mets null mais donne quand même le nom"""

    try:
        r = requests.post(
            "https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "mistral-small-latest",
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
                "temperature": 0.1  # Très bas pour être précis
            },
            timeout=30
        )
        
        if r.status_code == 200:
            content = r.json()['choices'][0]['message']['content']
            result = json.loads(content)
            
            # Log du résultat
            if result.get('parent_org_name'):
                log(f"✅ Mistral Parent: {result['parent_org_name']} ({result.get('parent_org_qid', '?')})", "OK")
            else:
                log("Mistral: pas de parent trouvé", "WARN")
            
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
                st.rerun()
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
                if "ERROR" in entry or "❌" in entry:
                    st.error(entry)
                elif "OK" in entry or "✅" in entry:
                    st.success(entry)
                elif "PARENT" in entry or "🔗" in entry:
                    st.info(entry)
                else:
                    st.caption(entry)
    
    st.divider()
    st.session_state.mistral_key = st.text_input("🔑 Clé Mistral", st.session_state.mistral_key, type="password")
    
    st.divider()
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
            if st.button(f"{item['qid']}: {item['label'][:22]}", key=f"w{i}", use_container_width=True):
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
                e.parent_org_qid = details['parent_qid']
                e.parent_org_name = details['parent_name']
                e.parent_source = details['parent_source']
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
                st.rerun()


# ============================================================================
# MAIN
# ============================================================================
e = st.session_state.entity

if e.name or e.qid or e.siren:
    # Metrics avec Parent
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Score", f"{e.score()}%")
    col2.metric("QID", e.qid or "—")
    col3.metric("SIREN", e.siren or "—")
    
    if e.parent_org_qid:
        col4.metric("🔗 Parent", f"{e.parent_org_qid}", delta=e.parent_source)
    else:
        col4.metric("Parent", "—")
    
    # Tabs
    tabs = st.tabs(["🆔 Identité", "🔗 Filiation", "🪄 GEO Magic", "📱 Social", "💾 JSON-LD"])
    
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            e.org_type = st.selectbox("Type", ["Organization", "Corporation", "LocalBusiness", "BankOrCreditUnion"])
            e.name = st.text_input("Nom", e.name)
            e.legal_name = st.text_input("Raison sociale", e.legal_name)
            e.siren = st.text_input("SIREN", e.siren)
        with c2:
            e.qid = st.text_input("QID", e.qid)
            e.lei = st.text_input("LEI", e.lei)
            e.website = st.text_input("Site web", e.website)
            e.address = st.text_input("Adresse", e.address)
    
    with tabs[1]:
        st.subheader("🔗 Filiation (Parent Organization)")
        
        # Info sur les sources
        st.info("""
        **Sources de filiation (par priorité):**
        1. **P749** - Parent Organization (Wikidata)
        2. **P127** - Owned By (Wikidata) 
        3. **Mistral AI** - Détection intelligente
        """)
        
        c1, c2 = st.columns(2)
        with c1:
            e.parent_org_name = st.text_input("Nom maison mère", e.parent_org_name)
        with c2:
            e.parent_org_qid = st.text_input("QID maison mère", e.parent_org_qid)
        
        e.parent_org_siren = st.text_input("SIREN maison mère", e.parent_org_siren)
        
        if e.parent_org_qid:
            source_badge = f"Source: {e.parent_source}" if e.parent_source else ""
            st.success(f"✅ **Filiation:** {e.name} → [{e.parent_org_name}](https://www.wikidata.org/wiki/{e.parent_org_qid}) {source_badge}")
        else:
            st.warning("⚠️ Pas de filiation trouvée. Clique sur **GEO Magic** pour la détecter via Mistral AI.")
            
            # Bouton rapide pour Mistral
            if st.button("🪄 Détecter Parent avec Mistral", type="primary"):
                if st.session_state.mistral_key:
                    with st.spinner("Mistral analyse..."):
                        result = mistral_optimize(st.session_state.mistral_key, e)
                    if result and result.get('parent_org_name'):
                        e.parent_org_name = result['parent_org_name']
                        e.parent_org_qid = result.get('parent_org_qid', '')
                        e.parent_source = "Mistral"
                        
                        # Si on a le nom mais pas le QID, on cherche
                        if e.parent_org_name and not e.parent_org_qid:
                            e.parent_org_qid = WikidataAPI.search_parent_qid(e.parent_org_name)
                        
                        st.rerun()
                    else:
                        st.error("Mistral n'a pas trouvé de parent")
                else:
                    st.error("🔑 Clé Mistral requise")
    
    with tabs[2]:
        st.subheader("🪄 GEO Magic (Mistral AI)")
        
        if st.button("🪄 Auto-Optimize Complet", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Mistral en cours..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                
                if result:
                    e.description_fr = result.get('description_fr', e.description_fr)
                    e.description_en = result.get('description_en', e.description_en)
                    e.expertise_fr = result.get('expertise_fr', e.expertise_fr)
                    e.expertise_en = result.get('expertise_en', e.expertise_en)
                    
                    # Filiation
                    if not e.parent_org_name and result.get('parent_org_name'):
                        e.parent_org_name = result['parent_org_name']
                        e.parent_source = "Mistral"
                    if not e.parent_org_qid and result.get('parent_org_qid'):
                        e.parent_org_qid = result['parent_org_qid']
                    
                    # Si on a le nom mais pas le QID, on cherche
                    if e.parent_org_name and not e.parent_org_qid:
                        e.parent_org_qid = WikidataAPI.search_parent_qid(e.parent_org_name)
                    
                    st.rerun()
            else:
                st.error("🔑 Clé Mistral requise")
        
        e.description_fr = st.text_area("Description FR", e.description_fr, height=100)
        e.description_en = st.text_area("Description EN", e.description_en, height=100)
        c1, c2 = st.columns(2)
        with c1:
            e.expertise_fr = st.text_input("Expertise FR", e.expertise_fr)
        with c2:
            e.expertise_en = st.text_input("Expertise EN", e.expertise_en)
    
    with tabs[3]:
        social = st.session_state.social_links
        c1, c2 = st.columns(2)
        with c1:
            social['linkedin'] = st.text_input("LinkedIn", social['linkedin'])
            social['twitter'] = st.text_input("Twitter", social['twitter'])
        with c2:
            social['facebook'] = st.text_input("Facebook", social['facebook'])
            social['youtube'] = st.text_input("YouTube", social['youtube'])
    
    with tabs[4]:
        # JSON-LD
        same_as = [f"https://www.wikidata.org/wiki/{e.qid}"] if e.qid else []
        same_as.extend([v for v in st.session_state.social_links.values() if v])
        
        json_ld = {
            "@context": "https://schema.org",
            "@type": e.org_type,
            "name": e.name
        }
        if e.website:
            json_ld["url"] = e.website
        if e.siren:
            json_ld["taxID"] = f"FR{e.siren}"
        if same_as:
            json_ld["sameAs"] = same_as
        if e.parent_org_name:
            json_ld["parentOrganization"] = {
                "@type": "Organization",
                "name": e.parent_org_name
            }
            if e.parent_org_qid:
                json_ld["parentOrganization"]["sameAs"] = f"https://www.wikidata.org/wiki/{e.parent_org_qid}"
        
        st.json(json_ld)
        st.download_button("💾 Télécharger", json.dumps(json_ld, indent=2, ensure_ascii=False), "schema.json")

else:
    st.info("👈 Recherche une organisation")
    st.markdown(f"""
    ### v{VERSION} - Filiation Enhanced
    
    **Nouvelles sources de filiation:**
    - P749 (parent organization)
    - P127 (owned by) - fallback
    - Mistral AI avec prompt optimisé
    
    **Test:** Cherche "Boursorama" puis clique sur **GEO Magic** pour détecter Société Générale comme parent!
    """)

st.divider()
st.caption(f"🛡️ AAS v{VERSION} | {BUILD_ID}")
