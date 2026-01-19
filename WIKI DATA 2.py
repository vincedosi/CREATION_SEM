"""
🛡️ Architecte d'Autorité Sémantique v8.4
=========================================
- SIREN maison mère auto-récupéré via INSEE
- RS: LinkedIn, Twitter/X, Facebook, Instagram, TikTok, YouTube
- Filiation: P749 + P127 + Mistral
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
VERSION = "8.4.0"
BUILD_ID = "BUILD-840-SIREN-PARENT"

# ============================================================================
# CONFIG
# ============================================================================
st.set_page_config(page_title=f"AAS v{VERSION}", page_icon="🛡️", layout="wide")

st.markdown(f"""
<div style="background: linear-gradient(90deg, #11998e 0%, #38ef7d 100%); color: white; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-weight: bold;">
    🛡️ AAS v{VERSION} | {BUILD_ID}
</div>
""", unsafe_allow_html=True)

# ============================================================================
# SESSION STATE
# ============================================================================
if 'logs' not in st.session_state: st.session_state.logs = []
if 'entity' not in st.session_state: st.session_state.entity = None
if 'wiki_results' not in st.session_state: st.session_state.wiki_results = []
if 'insee_results' not in st.session_state: st.session_state.insee_results = []
if 'social_links' not in st.session_state: 
    st.session_state.social_links = {'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '', 'tiktok': '', 'youtube': ''}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'mistral_key' not in st.session_state: st.session_state.mistral_key = ''

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "OK": "✅", "ERROR": "❌", "WARN": "⚠️", "HTTP": "🌐"}
    st.session_state.logs.append(f"{icons.get(level, '•')} [{ts}] {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs = st.session_state.logs[-50:]

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
    parent_org_siren: str = ""  # SIREN maison mère
    parent_source: str = ""
    address: str = ""

    def score(self) -> int:
        s = 0
        if self.qid: s += 15
        if self.siren: s += 15
        if self.lei: s += 10
        if self.website: s += 15
        if self.parent_org_qid: s += 15
        if self.parent_org_siren: s += 10  # Bonus SIREN parent
        if self.expertise_fr: s += 10
        if self.description_fr: s += 10
        return min(s, 100)

if st.session_state.entity is None:
    st.session_state.entity = Entity()

# ============================================================================
# WIKIDATA API
# ============================================================================
class WikidataAPI:
    BASE_URL = "https://www.wikidata.org/w/api.php"
    HEADERS = {"User-Agent": f"AAS/{VERSION}", "Accept": "application/json"}
    
    @staticmethod
    def search(query: str) -> List[Dict]:
        log(f"Wikidata: '{query}'", "HTTP")
        try:
            r = requests.get(WikidataAPI.BASE_URL, params={
                "action": "wbsearchentities", "search": query, "language": "fr",
                "uselang": "fr", "format": "json", "limit": 12, "type": "item"
            }, headers=WikidataAPI.HEADERS, timeout=20)
            if r.status_code == 200:
                results = r.json().get('search', [])
                log(f"{len(results)} résultats", "OK")
                return [{'qid': i['id'], 'label': i.get('label', i['id']), 'desc': i.get('description', '')} for i in results]
        except Exception as e:
            log(f"Erreur: {e}", "ERROR")
        return []
    
    @staticmethod
    def get_entity(qid: str) -> Dict:
        log(f"Get: {qid}", "HTTP")
        result = {"name_fr": "", "name_en": "", "desc_fr": "", "desc_en": "", "siren": "", "lei": "", "website": "", "parent_qid": "", "parent_name": "", "parent_source": ""}
        
        try:
            r = requests.get(WikidataAPI.BASE_URL, params={
                "action": "wbgetentities", "ids": qid, "languages": "fr|en",
                "props": "labels|descriptions|claims", "format": "json"
            }, headers=WikidataAPI.HEADERS, timeout=20)
            
            if r.status_code == 200:
                entity = r.json().get('entities', {}).get(qid, {})
                if not entity: return result
                
                labels = entity.get('labels', {})
                descs = entity.get('descriptions', {})
                claims = entity.get('claims', {})
                
                result["name_fr"] = labels.get('fr', {}).get('value', '')
                result["name_en"] = labels.get('en', {}).get('value', '')
                result["desc_fr"] = descs.get('fr', {}).get('value', '')
                result["desc_en"] = descs.get('en', {}).get('value', '')
                
                # SIREN P1616
                if 'P1616' in claims:
                    try: result["siren"] = claims['P1616'][0]['mainsnak']['datavalue']['value']
                    except: pass
                
                # LEI P1278
                if 'P1278' in claims:
                    try: result["lei"] = claims['P1278'][0]['mainsnak']['datavalue']['value']
                    except: pass
                
                # Website P856
                if 'P856' in claims:
                    try: result["website"] = claims['P856'][0]['mainsnak']['datavalue']['value']
                    except: pass
                
                # Parent P749
                if 'P749' in claims:
                    try:
                        pval = claims['P749'][0]['mainsnak']['datavalue']['value']
                        result["parent_qid"] = pval.get('id', '') if isinstance(pval, dict) else pval
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P749"
                            log(f"Parent P749: {result['parent_name']}", "OK")
                    except: pass
                
                # Parent P127 (fallback)
                if not result["parent_qid"] and 'P127' in claims:
                    try:
                        pval = claims['P127'][0]['mainsnak']['datavalue']['value']
                        result["parent_qid"] = pval.get('id', '') if isinstance(pval, dict) else pval
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P127"
                            log(f"Parent P127: {result['parent_name']}", "OK")
                    except: pass
                
                if not result["parent_qid"]:
                    log("Pas de parent Wikidata", "WARN")
                    
        except Exception as e:
            log(f"Exception: {e}", "ERROR")
        return result
    
    @staticmethod
    def get_label(qid: str) -> str:
        try:
            r = requests.get(WikidataAPI.BASE_URL, params={
                "action": "wbgetentities", "ids": qid, "languages": "fr|en", "props": "labels", "format": "json"
            }, headers=WikidataAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                labels = r.json().get('entities', {}).get(qid, {}).get('labels', {})
                return labels.get('fr', {}).get('value', '') or labels.get('en', {}).get('value', qid)
        except: pass
        return qid
    
    @staticmethod
    def get_siren(qid: str) -> str:
        """Récupère le SIREN d'un QID."""
        try:
            r = requests.get(WikidataAPI.BASE_URL, params={
                "action": "wbgetentities", "ids": qid, "props": "claims", "format": "json"
            }, headers=WikidataAPI.HEADERS, timeout=10)
            if r.status_code == 200:
                claims = r.json().get('entities', {}).get(qid, {}).get('claims', {})
                if 'P1616' in claims:
                    return claims['P1616'][0]['mainsnak']['datavalue']['value']
        except: pass
        return ""

# ============================================================================
# INSEE API
# ============================================================================
class INSEEAPI:
    @staticmethod
    def search(query: str) -> List[Dict]:
        log(f"INSEE: '{query}'", "HTTP")
        try:
            r = requests.get("https://recherche-entreprises.api.gouv.fr/search", params={"q": query, "per_page": 10}, timeout=15)
            if r.status_code == 200:
                results = r.json().get('results', [])
                log(f"{len(results)} résultats", "OK")
                return [{
                    'siren': i.get('siren', ''),
                    'siret': i.get('siege', {}).get('siret', ''),
                    'name': i.get('nom_complet', ''),
                    'legal_name': i.get('nom_raison_sociale', ''),
                    'naf': i.get('activite_principale', ''),
                    'address': f"{i.get('siege', {}).get('adresse', '')} {i.get('siege', {}).get('code_postal', '')} {i.get('siege', {}).get('commune', '')}",
                    'active': i.get('etat_administratif') == 'A'
                } for i in results]
        except Exception as e:
            log(f"INSEE error: {e}", "ERROR")
        return []
    
    @staticmethod
    def get_siren_by_name(name: str) -> str:
        """Recherche SIREN par nom d'entreprise."""
        log(f"INSEE SIREN: '{name}'", "HTTP")
        try:
            r = requests.get("https://recherche-entreprises.api.gouv.fr/search", params={"q": name, "per_page": 1}, timeout=10)
            if r.status_code == 200:
                results = r.json().get('results', [])
                if results:
                    siren = results[0].get('siren', '')
                    log(f"SIREN trouvé: {siren}", "OK")
                    return siren
        except: pass
        return ""

# ============================================================================
# MISTRAL API
# ============================================================================
def mistral_optimize(api_key: str, entity) -> Optional[Dict]:
    if not api_key: return None
    log("Mistral...", "HTTP")
    
    prompt = f"""Expert entreprises françaises. Analyse:
- Nom: {entity.name}
- SIREN: {entity.siren or 'N/A'}
- QID: {entity.qid or 'N/A'}

TROUVE LA MAISON MÈRE. Exemples:
- Boursorama/BoursoBank → Société Générale (Q270618)
- Hello Bank → BNP Paribas (Q499707)
- Fortuneo → Crédit Mutuel Arkéa

JSON STRICT:
{{"description_fr": "...", "description_en": "...", "expertise_fr": "A, B, C", "expertise_en": "X, Y, Z", "parent_org_name": "Nom exact ou null", "parent_org_qid": "Qxxxxxx ou null"}}"""

    try:
        r = requests.post("https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": prompt}],
                  "response_format": {"type": "json_object"}, "temperature": 0.1}, timeout=30)
        if r.status_code == 200:
            result = json.loads(r.json()['choices'][0]['message']['content'])
            if result.get('parent_org_name'):
                log(f"Parent Mistral: {result['parent_org_name']}", "OK")
            return result
    except Exception as e:
        log(f"Mistral error: {e}", "ERROR")
    return None

# ============================================================================
# AUTH
# ============================================================================
if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align:center'>🔐 Accès</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.text_input("Mot de passe:", type="password", key="pwd") == "SEOTOOLS":
            if st.button("🔓 Entrer", type="primary", use_container_width=True):
                st.session_state.authenticated = True
                st.rerun()
    st.stop()

# ============================================================================
# SIDEBAR
# ============================================================================
with st.sidebar:
    with st.expander("📟 Logs", expanded=True):
        for entry in reversed(st.session_state.logs[-12:]):
            if "ERROR" in entry: st.error(entry)
            elif "OK" in entry: st.success(entry)
            else: st.caption(entry)
    
    st.divider()
    st.session_state.mistral_key = st.text_input("🔑 Mistral", st.session_state.mistral_key, type="password")
    
    st.divider()
    source = st.radio("Source", ["Wikidata", "INSEE", "Les deux"], horizontal=True)
    query = st.text_input("🔍 Organisation")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔎 Chercher", type="primary", use_container_width=True) and query:
            if source in ["Wikidata", "Les deux"]: st.session_state.wiki_results = WikidataAPI.search(query)
            if source in ["INSEE", "Les deux"]: st.session_state.insee_results = INSEEAPI.search(query)
            st.rerun()
    with c2:
        if st.button("🗑️ Reset", use_container_width=True):
            st.session_state.entity = Entity()
            st.session_state.wiki_results = []
            st.session_state.insee_results = []
            st.rerun()
    
    # Résultats
    if st.session_state.wiki_results:
        st.markdown("**🌐 Wikidata:**")
        for i, item in enumerate(st.session_state.wiki_results[:8]):
            if st.button(f"{item['qid']}: {item['label'][:20]}", key=f"w{i}", use_container_width=True):
                details = WikidataAPI.get_entity(item['qid'])
                e = st.session_state.entity
                e.qid, e.name, e.name_en = item['qid'], details['name_fr'] or item['label'], details['name_en']
                e.description_fr, e.description_en = details['desc_fr'], details['desc_en']
                e.siren, e.lei, e.website = e.siren or details['siren'], details['lei'], e.website or details['website']
                e.parent_org_qid, e.parent_org_name, e.parent_source = details['parent_qid'], details['parent_name'], details['parent_source']
                # Auto SIREN parent
                if e.parent_org_qid and not e.parent_org_siren:
                    e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                    if e.parent_org_siren: log(f"SIREN parent: {e.parent_org_siren}", "OK")
                st.rerun()
    
    if st.session_state.insee_results:
        st.markdown("**🏛️ INSEE:**")
        for i, item in enumerate(st.session_state.insee_results[:6]):
            if st.button(f"{'🟢' if item['active'] else '🔴'} {item['name'][:20]}", key=f"i{i}", use_container_width=True):
                e = st.session_state.entity
                e.name, e.legal_name, e.siren, e.siret = e.name or item['name'], item['legal_name'], item['siren'], item['siret']
                e.naf, e.address = item['naf'], item['address']
                st.rerun()

# ============================================================================
# MAIN
# ============================================================================
e = st.session_state.entity

if e.name or e.qid or e.siren:
    # Metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Score", f"{e.score()}%")
    m2.metric("QID", e.qid or "—")
    m3.metric("SIREN", e.siren or "—")
    m4.metric("Parent QID", e.parent_org_qid or "—")
    m5.metric("Parent SIREN", e.parent_org_siren or "—")
    
    tabs = st.tabs(["🆔 Identité", "🔗 Filiation", "🪄 GEO Magic", "📱 Réseaux Sociaux", "💾 JSON-LD"])
    
    # Identité
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
    
    # Filiation
    with tabs[1]:
        st.subheader("🔗 Filiation (Parent Organization)")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            e.parent_org_name = st.text_input("Nom maison mère", e.parent_org_name)
        with c2:
            e.parent_org_qid = st.text_input("QID maison mère", e.parent_org_qid)
        with c3:
            e.parent_org_siren = st.text_input("SIREN maison mère", e.parent_org_siren)
        
        if e.parent_org_qid:
            st.success(f"✅ {e.name} → [{e.parent_org_name}](https://www.wikidata.org/wiki/{e.parent_org_qid}) | SIREN: {e.parent_org_siren or 'N/A'}")
        else:
            st.warning("⚠️ Pas de filiation. Utilise Mistral ci-dessous.")
        
        if st.button("🪄 Détecter Parent (Mistral)", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Analyse..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                if result and result.get('parent_org_name'):
                    e.parent_org_name = result['parent_org_name']
                    e.parent_org_qid = result.get('parent_org_qid', '')
                    e.parent_source = "Mistral"
                    # Chercher SIREN parent
                    if e.parent_org_name and not e.parent_org_siren:
                        # Via Wikidata si on a le QID
                        if e.parent_org_qid:
                            e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                        # Sinon via INSEE
                        if not e.parent_org_siren:
                            e.parent_org_siren = INSEEAPI.get_siren_by_name(e.parent_org_name)
                    st.rerun()
            else:
                st.error("🔑 Clé Mistral requise")
    
    # GEO Magic
    with tabs[2]:
        if st.button("🪄 Auto-Optimize", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Mistral..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                if result:
                    e.description_fr = result.get('description_fr', e.description_fr)
                    e.description_en = result.get('description_en', e.description_en)
                    e.expertise_fr = result.get('expertise_fr', e.expertise_fr)
                    e.expertise_en = result.get('expertise_en', e.expertise_en)
                    if not e.parent_org_name and result.get('parent_org_name'):
                        e.parent_org_name, e.parent_org_qid, e.parent_source = result['parent_org_name'], result.get('parent_org_qid', ''), "Mistral"
                        if e.parent_org_qid: e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                        if not e.parent_org_siren: e.parent_org_siren = INSEEAPI.get_siren_by_name(e.parent_org_name)
                    st.rerun()
        
        e.description_fr = st.text_area("Description FR", e.description_fr, height=80)
        e.description_en = st.text_area("Description EN", e.description_en, height=80)
        c1, c2 = st.columns(2)
        with c1: e.expertise_fr = st.text_input("Expertise FR", e.expertise_fr)
        with c2: e.expertise_en = st.text_input("Expertise EN", e.expertise_en)
    
    # Réseaux Sociaux
    with tabs[3]:
        st.subheader("📱 Réseaux Sociaux (sameAs)")
        social = st.session_state.social_links
        c1, c2 = st.columns(2)
        with c1:
            social['linkedin'] = st.text_input("LinkedIn", social['linkedin'])
            social['twitter'] = st.text_input("Twitter/X", social['twitter'])
            social['facebook'] = st.text_input("Facebook", social['facebook'])
        with c2:
            social['instagram'] = st.text_input("Instagram", social['instagram'])
            social['tiktok'] = st.text_input("TikTok", social['tiktok'])
            social['youtube'] = st.text_input("YouTube", social['youtube'])
    
    # JSON-LD
    with tabs[4]:
        same_as = [f"https://www.wikidata.org/wiki/{e.qid}"] if e.qid else []
        same_as.extend([v for v in st.session_state.social_links.values() if v])
        
        identifiers = []
        if e.siren: identifiers.append({"@type": "PropertyValue", "propertyID": "SIREN", "value": e.siren})
        if e.lei: identifiers.append({"@type": "PropertyValue", "propertyID": "LEI", "value": e.lei})
        
        json_ld = {"@context": "https://schema.org", "@type": e.org_type, "name": e.name}
        if e.legal_name: json_ld["legalName"] = e.legal_name
        if e.website: json_ld["@id"], json_ld["url"] = f"{e.website.rstrip('/')}/#organization", e.website
        if e.description_fr: json_ld["description"] = e.description_fr
        if e.siren: json_ld["taxID"] = f"FR{e.siren}"
        if identifiers: json_ld["identifier"] = identifiers
        if same_as: json_ld["sameAs"] = same_as
        if e.address: json_ld["address"] = {"@type": "PostalAddress", "streetAddress": e.address}
        if e.expertise_fr: json_ld["knowsAbout"] = [x.strip() for x in e.expertise_fr.split(',')]
        if e.parent_org_name:
            json_ld["parentOrganization"] = {"@type": "Organization", "name": e.parent_org_name}
            if e.parent_org_qid: json_ld["parentOrganization"]["sameAs"] = f"https://www.wikidata.org/wiki/{e.parent_org_qid}"
            if e.parent_org_siren: json_ld["parentOrganization"]["taxID"] = f"FR{e.parent_org_siren}"
        
        st.json(json_ld)
        c1, c2 = st.columns(2)
        with c1: st.download_button("📄 JSON-LD", json.dumps(json_ld, indent=2, ensure_ascii=False), "schema.json")
        with c2: st.download_button("💾 Config", json.dumps({"entity": asdict(e), "social": st.session_state.social_links}, indent=2, ensure_ascii=False), "config.json")

else:
    st.info("👈 Recherche une organisation")
    st.markdown(f"""
    ### v{VERSION} - Nouveautés
    - **SIREN maison mère** auto-récupéré (Wikidata + INSEE)
    - **Réseaux sociaux** : LinkedIn, Twitter/X, Facebook, Instagram, TikTok, YouTube
    - **Filiation** : P749 + P127 + Mistral
    """)

st.divider()
st.caption(f"🛡️ AAS v{VERSION} | {BUILD_ID}")
