"""
🛡️ Architecte d'Autorité Sémantique v8.5
=========================================
JSON-LD COMPLET + VALIDATION
- Template JSON-LD parfait (logo, slogan, founders, rating, etc.)
- Liens vers validateurs (Schema.org, Google Rich Results)
- SIREN maison mère auto
- RS: LinkedIn, Twitter/X, Facebook, Instagram, TikTok, YouTube
"""

import streamlit as st
import requests
import json
import time
import urllib.parse
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from datetime import datetime

# ============================================================================
# VERSION
# ============================================================================
VERSION = "8.5.0"
BUILD_ID = "BUILD-850-JSONLD-COMPLETE"

# ============================================================================
# CONFIG
# ============================================================================
st.set_page_config(page_title=f"AAS v{VERSION}", page_icon="🛡️", layout="wide")

st.markdown(f"""
<div style="background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 20px; border-radius: 8px; margin-bottom: 20px; text-align: center; font-weight: bold;">
    🛡️ AAS v{VERSION} | {BUILD_ID} | JSON-LD Complet + Validation
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
    st.session_state.social_links = {'linkedin': '', 'twitter': '', 'facebook': '', 'instagram': '', 'tiktok': '', 'youtube': '', 'wikipedia': ''}
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'mistral_key' not in st.session_state: st.session_state.mistral_key = ''

def log(msg: str, level: str = "INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    icons = {"INFO": "ℹ️", "OK": "✅", "ERROR": "❌", "WARN": "⚠️", "HTTP": "🌐"}
    st.session_state.logs.append(f"{icons.get(level, '•')} [{ts}] {msg}")
    if len(st.session_state.logs) > 50: st.session_state.logs = st.session_state.logs[-50:]

# ============================================================================
# DATA CLASS - COMPLET
# ============================================================================
@dataclass
class Entity:
    # Identité
    name: str = ""
    name_en: str = ""
    legal_name: str = ""
    alternate_names: str = ""  # Séparés par virgule
    description_fr: str = ""
    description_en: str = ""
    slogan: str = ""
    
    # Expertise
    expertise_fr: str = ""
    expertise_en: str = ""
    
    # Identifiants
    qid: str = ""
    siren: str = ""
    siret: str = ""
    lei: str = ""
    naf: str = ""
    
    # Web
    website: str = ""
    logo_url: str = ""
    logo_width: str = "600"
    logo_height: str = "60"
    
    # Type
    org_type: str = "Corporation"
    
    # Filiation
    parent_org_name: str = ""
    parent_org_qid: str = ""
    parent_org_siren: str = ""
    parent_source: str = ""
    
    # Adresse
    street_address: str = ""
    city: str = ""
    postal_code: str = ""
    country: str = "FR"
    
    # Contact
    phone: str = ""
    email: str = ""
    contact_type: str = "customer service"
    languages: str = "French, English"
    
    # Histoire
    founding_date: str = ""
    founder_name: str = ""
    founder_linkedin: str = ""
    
    # Avis
    rating_value: str = ""
    review_count: str = ""
    
    # Recherche interne
    search_url_template: str = ""
    
    # Zone servie
    area_served: str = "France"

    def score(self) -> int:
        s = 0
        if self.qid: s += 10
        if self.siren: s += 10
        if self.lei: s += 5
        if self.website: s += 10
        if self.logo_url: s += 5
        if self.parent_org_qid: s += 10
        if self.parent_org_siren: s += 5
        if self.expertise_fr: s += 5
        if self.description_fr: s += 10
        if self.street_address and self.city: s += 5
        if self.phone or self.email: s += 5
        if self.founding_date: s += 5
        if self.rating_value: s += 5
        if self.slogan: s += 5
        if self.alternate_names: s += 5
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
        result = {"name_fr": "", "name_en": "", "desc_fr": "", "desc_en": "", "siren": "", "lei": "", "website": "", "parent_qid": "", "parent_name": "", "parent_source": "", "founding_date": ""}
        
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
                
                # Founding date P571
                if 'P571' in claims:
                    try: 
                        time_val = claims['P571'][0]['mainsnak']['datavalue']['value']['time']
                        result["founding_date"] = time_val[1:11]  # +YYYY-MM-DD -> YYYY-MM-DD
                    except: pass
                
                # Parent P749
                if 'P749' in claims:
                    try:
                        pval = claims['P749'][0]['mainsnak']['datavalue']['value']
                        result["parent_qid"] = pval.get('id', '') if isinstance(pval, dict) else pval
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P749"
                    except: pass
                
                # Parent P127 (fallback)
                if not result["parent_qid"] and 'P127' in claims:
                    try:
                        pval = claims['P127'][0]['mainsnak']['datavalue']['value']
                        result["parent_qid"] = pval.get('id', '') if isinstance(pval, dict) else pval
                        if result["parent_qid"]:
                            result["parent_name"] = WikidataAPI.get_label(result["parent_qid"])
                            result["parent_source"] = "P127"
                    except: pass
                    
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
                    'street': i.get('siege', {}).get('adresse', ''),
                    'city': i.get('siege', {}).get('commune', ''),
                    'postal_code': i.get('siege', {}).get('code_postal', ''),
                    'active': i.get('etat_administratif') == 'A',
                    'creation_date': i.get('date_creation', '')
                } for i in results]
        except Exception as e:
            log(f"INSEE error: {e}", "ERROR")
        return []
    
    @staticmethod
    def get_siren_by_name(name: str) -> str:
        try:
            r = requests.get("https://recherche-entreprises.api.gouv.fr/search", params={"q": name, "per_page": 1}, timeout=10)
            if r.status_code == 200:
                results = r.json().get('results', [])
                if results:
                    return results[0].get('siren', '')
        except: pass
        return ""

# ============================================================================
# MISTRAL API
# ============================================================================
def mistral_optimize(api_key: str, entity) -> Optional[Dict]:
    if not api_key: return None
    log("Mistral...", "HTTP")
    
    prompt = f"""Expert SEO entreprises. Analyse:
- Nom: {entity.name}
- SIREN: {entity.siren or 'N/A'}
- QID: {entity.qid or 'N/A'}

TROUVE: maison mère, description SEO, slogan, expertise.
Exemples filiation: Boursorama→Société Générale (Q270618), Hello Bank→BNP Paribas

JSON STRICT:
{{"description_fr": "150-200 car SEO", "description_en": "...", "expertise_fr": "A, B, C", "expertise_en": "X, Y, Z", "slogan": "Phrase accrocheuse ou null", "parent_org_name": "Nom ou null", "parent_org_qid": "Qxxxxxx ou null"}}"""

    try:
        r = requests.post("https://api.mistral.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "mistral-small-latest", "messages": [{"role": "user", "content": prompt}],
                  "response_format": {"type": "json_object"}, "temperature": 0.1}, timeout=30)
        if r.status_code == 200:
            result = json.loads(r.json()['choices'][0]['message']['content'])
            log(f"Mistral OK", "OK")
            return result
    except Exception as e:
        log(f"Mistral error: {e}", "ERROR")
    return None

# ============================================================================
# JSON-LD BUILDER - COMPLET
# ============================================================================
def build_jsonld(e, social_links: Dict) -> Dict:
    """Construit le JSON-LD complet selon le template idéal."""
    
    # Base
    json_ld = {
        "@context": "https://schema.org",
        "@type": e.org_type,
        "name": e.name
    }
    
    # Nom légal
    if e.legal_name:
        json_ld["legalName"] = e.legal_name
    
    # Noms alternatifs
    if e.alternate_names:
        names = [n.strip() for n in e.alternate_names.split(',') if n.strip()]
        if names:
            json_ld["alternateName"] = names
    
    # URL & ID
    if e.website:
        json_ld["@id"] = f"{e.website.rstrip('/')}/#organization"
        json_ld["url"] = e.website
    
    # Logo
    if e.logo_url:
        json_ld["logo"] = {
            "@type": "ImageObject",
            "url": e.logo_url,
            "width": e.logo_width,
            "height": e.logo_height
        }
    
    # Description & Slogan
    if e.description_fr:
        json_ld["description"] = e.description_fr
    if e.slogan:
        json_ld["slogan"] = e.slogan
    
    # Identifiants légaux
    if e.siren:
        json_ld["taxID"] = f"FR{e.siren}"
        json_ld["vatID"] = f"FR{e.siren}"
        json_ld["iso6523Code"] = f"0002:{e.siren}"
    
    # Identifiants structurés
    identifiers = []
    if e.siren:
        identifiers.append({"@type": "PropertyValue", "propertyID": "SIREN", "value": e.siren})
    if e.siret:
        identifiers.append({"@type": "PropertyValue", "propertyID": "SIRET", "value": e.siret})
    if e.lei:
        identifiers.append({"@type": "PropertyValue", "propertyID": "LEI", "value": e.lei})
    if identifiers:
        json_ld["identifier"] = identifiers
    
    # sameAs (Knowledge Graph)
    same_as = []
    if e.qid:
        same_as.append(f"https://www.wikidata.org/wiki/{e.qid}")
    if social_links.get('wikipedia'):
        same_as.append(social_links['wikipedia'])
    if social_links.get('linkedin'):
        same_as.append(social_links['linkedin'])
    if social_links.get('twitter'):
        same_as.append(social_links['twitter'])
    if social_links.get('facebook'):
        same_as.append(social_links['facebook'])
    if social_links.get('instagram'):
        same_as.append(social_links['instagram'])
    if social_links.get('tiktok'):
        same_as.append(social_links['tiktok'])
    if social_links.get('youtube'):
        same_as.append(social_links['youtube'])
    if same_as:
        json_ld["sameAs"] = same_as
    
    # Expertise (knowsAbout)
    if e.expertise_fr:
        json_ld["knowsAbout"] = [x.strip() for x in e.expertise_fr.split(',') if x.strip()]
    
    # Zone servie
    if e.area_served:
        json_ld["areaServed"] = {
            "@type": "Country",
            "name": e.area_served
        }
    
    # Adresse
    if e.street_address or e.city:
        json_ld["address"] = {
            "@type": "PostalAddress",
            "streetAddress": e.street_address,
            "addressLocality": e.city,
            "postalCode": e.postal_code,
            "addressCountry": e.country
        }
    
    # Contact
    if e.phone or e.email:
        contact = {"@type": "ContactPoint", "contactType": e.contact_type}
        if e.phone:
            contact["telephone"] = e.phone
        if e.email:
            contact["email"] = e.email
        if e.languages:
            contact["availableLanguage"] = [l.strip() for l in e.languages.split(',')]
        json_ld["contactPoint"] = [contact]
    
    # Histoire
    if e.founding_date:
        json_ld["foundingDate"] = e.founding_date
    
    if e.founder_name:
        founder = {"@type": "Person", "name": e.founder_name}
        if e.founder_linkedin:
            founder["sameAs"] = e.founder_linkedin
        json_ld["founders"] = [founder]
    
    # Filiation
    if e.parent_org_name:
        parent = {"@type": "Organization", "name": e.parent_org_name}
        if e.parent_org_qid:
            parent["sameAs"] = f"https://www.wikidata.org/wiki/{e.parent_org_qid}"
        if e.parent_org_siren:
            parent["taxID"] = f"FR{e.parent_org_siren}"
        json_ld["parentOrganization"] = parent
    
    # Avis
    if e.rating_value and e.review_count:
        json_ld["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": e.rating_value,
            "reviewCount": e.review_count,
            "bestRating": "5",
            "worstRating": "1"
        }
    
    # Recherche interne
    if e.search_url_template:
        json_ld["potentialAction"] = {
            "@type": "SearchAction",
            "target": e.search_url_template,
            "query-input": "required name=search_term_string"
        }
    
    return json_ld

# ============================================================================
# VALIDATION HELPERS
# ============================================================================
def get_validator_urls(json_ld: Dict) -> Dict[str, str]:
    """Génère les URLs des validateurs avec le JSON encodé."""
    json_str = json.dumps(json_ld, ensure_ascii=False)
    encoded = urllib.parse.quote(json_str, safe='')
    
    return {
        "schema_org": f"https://validator.schema.org/#url=data:application/ld+json,{encoded}",
        "google_rich": f"https://search.google.com/test/rich-results?code={encoded}",
        "wordlift": "https://wordlift.io/schema-markup-validator/"
    }

def validate_jsonld_local(json_ld: Dict) -> List[str]:
    """Validation locale basique."""
    errors = []
    warnings = []
    
    # Champs requis
    if not json_ld.get("name"):
        errors.append("❌ 'name' est requis")
    if not json_ld.get("@type"):
        errors.append("❌ '@type' est requis")
    if not json_ld.get("@context"):
        errors.append("❌ '@context' est requis")
    
    # Recommandations
    if not json_ld.get("url"):
        warnings.append("⚠️ 'url' recommandé")
    if not json_ld.get("logo"):
        warnings.append("⚠️ 'logo' recommandé pour les rich results")
    if not json_ld.get("sameAs"):
        warnings.append("⚠️ 'sameAs' recommandé pour l'autorité")
    if not json_ld.get("description"):
        warnings.append("⚠️ 'description' recommandé")
    if not json_ld.get("address"):
        warnings.append("⚠️ 'address' recommandé pour LocalBusiness")
    
    return errors + warnings

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
    with st.expander("📟 Logs", expanded=False):
        for entry in reversed(st.session_state.logs[-10:]):
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
            if st.button(f"{item['qid']}: {item['label'][:18]}", key=f"w{i}", use_container_width=True):
                details = WikidataAPI.get_entity(item['qid'])
                e = st.session_state.entity
                e.qid, e.name, e.name_en = item['qid'], details['name_fr'] or item['label'], details['name_en']
                e.description_fr, e.description_en = details['desc_fr'], details['desc_en']
                e.siren, e.lei, e.website = e.siren or details['siren'], details['lei'], e.website or details['website']
                e.founding_date = details.get('founding_date', '')
                e.parent_org_qid, e.parent_org_name, e.parent_source = details['parent_qid'], details['parent_name'], details['parent_source']
                if e.parent_org_qid and not e.parent_org_siren:
                    e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                st.rerun()
    
    if st.session_state.insee_results:
        st.markdown("**🏛️ INSEE:**")
        for i, item in enumerate(st.session_state.insee_results[:6]):
            if st.button(f"{'🟢' if item['active'] else '🔴'} {item['name'][:18]}", key=f"i{i}", use_container_width=True):
                e = st.session_state.entity
                e.name, e.legal_name, e.siren, e.siret = e.name or item['name'], item['legal_name'], item['siren'], item['siret']
                e.naf, e.street_address, e.city, e.postal_code = item['naf'], item['street'], item['city'], item['postal_code']
                if item.get('creation_date'):
                    e.founding_date = item['creation_date']
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
    m4.metric("Parent", e.parent_org_qid or "—")
    m5.metric("SIREN Parent", e.parent_org_siren or "—")
    
    tabs = st.tabs(["🆔 Identité", "📍 Contact", "🔗 Filiation", "📱 Social", "⭐ Preuves", "🪄 Magic", "💾 JSON-LD"])
    
    # Tab Identité
    with tabs[0]:
        c1, c2 = st.columns(2)
        with c1:
            e.org_type = st.selectbox("Type Schema.org", ["Corporation", "Organization", "LocalBusiness", "BankOrCreditUnion", "InsuranceAgency", "FinancialService"])
            e.name = st.text_input("Nom commercial", e.name)
            e.legal_name = st.text_input("Raison sociale", e.legal_name)
            e.alternate_names = st.text_input("Noms alternatifs (virgules)", e.alternate_names, placeholder="BoursoBank, Bourso")
            e.slogan = st.text_input("Slogan", e.slogan, placeholder="Votre promesse client")
        with c2:
            e.qid = st.text_input("QID Wikidata", e.qid)
            e.siren = st.text_input("SIREN", e.siren)
            e.siret = st.text_input("SIRET", e.siret)
            e.lei = st.text_input("LEI", e.lei)
            e.founding_date = st.text_input("Date création (YYYY-MM-DD)", e.founding_date)
        
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            e.website = st.text_input("Site web", e.website)
        with c2:
            e.logo_url = st.text_input("URL Logo", e.logo_url, placeholder="https://www.site.com/logo.png")
    
    # Tab Contact
    with tabs[1]:
        c1, c2 = st.columns(2)
        with c1:
            e.street_address = st.text_input("Adresse", e.street_address)
            e.city = st.text_input("Ville", e.city)
            e.postal_code = st.text_input("Code postal", e.postal_code)
            e.country = st.text_input("Pays (code)", e.country)
        with c2:
            e.phone = st.text_input("Téléphone", e.phone, placeholder="+33-1-XX-XX-XX-XX")
            e.email = st.text_input("Email contact", e.email)
            e.contact_type = st.selectbox("Type contact", ["customer service", "technical support", "sales", "billing"])
            e.languages = st.text_input("Langues (virgules)", e.languages)
        
        e.area_served = st.text_input("Zone servie", e.area_served)
    
    # Tab Filiation
    with tabs[2]:
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
        
        if st.button("🪄 Détecter Parent (Mistral)", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Analyse..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                if result and result.get('parent_org_name'):
                    e.parent_org_name = result['parent_org_name']
                    e.parent_org_qid = result.get('parent_org_qid', '')
                    e.parent_source = "Mistral"
                    if e.parent_org_qid:
                        e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                    if not e.parent_org_siren and e.parent_org_name:
                        e.parent_org_siren = INSEEAPI.get_siren_by_name(e.parent_org_name)
                    st.rerun()
            else:
                st.error("🔑 Clé Mistral requise")
    
    # Tab Social
    with tabs[3]:
        st.subheader("📱 Réseaux Sociaux & Knowledge Graph")
        social = st.session_state.social_links
        c1, c2 = st.columns(2)
        with c1:
            social['wikipedia'] = st.text_input("Wikipedia FR", social['wikipedia'], placeholder="https://fr.wikipedia.org/wiki/...")
            social['linkedin'] = st.text_input("LinkedIn", social['linkedin'])
            social['twitter'] = st.text_input("Twitter/X", social['twitter'])
            social['facebook'] = st.text_input("Facebook", social['facebook'])
        with c2:
            social['instagram'] = st.text_input("Instagram", social['instagram'])
            social['tiktok'] = st.text_input("TikTok", social['tiktok'])
            social['youtube'] = st.text_input("YouTube", social['youtube'])
    
    # Tab Preuves
    with tabs[4]:
        st.subheader("⭐ Preuves Sociales & Confiance")
        
        c1, c2 = st.columns(2)
        with c1:
            e.rating_value = st.text_input("Note moyenne", e.rating_value, placeholder="4.8")
            e.review_count = st.text_input("Nombre d'avis", e.review_count, placeholder="1250")
        with c2:
            e.founder_name = st.text_input("Nom fondateur", e.founder_name)
            e.founder_linkedin = st.text_input("LinkedIn fondateur", e.founder_linkedin)
        
        st.divider()
        st.subheader("🔍 Recherche interne (Sitelinks Searchbox)")
        e.search_url_template = st.text_input("URL recherche", e.search_url_template, 
            placeholder="https://www.site.com/search?q={search_term_string}")
    
    # Tab Magic
    with tabs[5]:
        if st.button("🪄 Auto-Optimize Complet", type="primary"):
            if st.session_state.mistral_key:
                with st.spinner("Mistral..."):
                    result = mistral_optimize(st.session_state.mistral_key, e)
                if result:
                    e.description_fr = result.get('description_fr', e.description_fr)
                    e.description_en = result.get('description_en', e.description_en)
                    e.expertise_fr = result.get('expertise_fr', e.expertise_fr)
                    e.expertise_en = result.get('expertise_en', e.expertise_en)
                    e.slogan = result.get('slogan', e.slogan) or e.slogan
                    if not e.parent_org_name and result.get('parent_org_name'):
                        e.parent_org_name, e.parent_org_qid = result['parent_org_name'], result.get('parent_org_qid', '')
                        e.parent_source = "Mistral"
                        if e.parent_org_qid:
                            e.parent_org_siren = WikidataAPI.get_siren(e.parent_org_qid)
                    st.rerun()
        
        e.description_fr = st.text_area("Description FR (SEO)", e.description_fr, height=80)
        e.description_en = st.text_area("Description EN", e.description_en, height=80)
        c1, c2 = st.columns(2)
        with c1: e.expertise_fr = st.text_input("Expertise FR", e.expertise_fr, placeholder="Banque en ligne, Épargne, Bourse")
        with c2: e.expertise_en = st.text_input("Expertise EN", e.expertise_en)
    
    # Tab JSON-LD
    with tabs[6]:
        st.subheader("💾 JSON-LD Complet")
        
        json_ld = build_jsonld(e, st.session_state.social_links)
        
        # Validation locale
        validation = validate_jsonld_local(json_ld)
        if validation:
            with st.expander("📋 Validation", expanded=True):
                for msg in validation:
                    if msg.startswith("❌"):
                        st.error(msg)
                    else:
                        st.warning(msg)
        else:
            st.success("✅ JSON-LD valide localement!")
        
        # Liens validateurs
        st.subheader("🔗 Tester sur les validateurs")
        
        json_str = json.dumps(json_ld, ensure_ascii=False)
        encoded_json = urllib.parse.quote(json_str, safe='')
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.link_button("🌐 Schema.org Validator", f"https://validator.schema.org/#url=data:application/ld+json,{encoded_json}", use_container_width=True)
        with c2:
            st.link_button("🔍 Google Rich Results", "https://search.google.com/test/rich-results", use_container_width=True)
            st.caption("Colle le JSON ci-dessous")
        with c3:
            st.link_button("📊 WordLift Validator", "https://wordlift.io/schema-markup-validator/", use_container_width=True)
        
        # JSON affiché
        st.json(json_ld)
        
        # Boutons export
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("📄 JSON-LD", json.dumps(json_ld, indent=2, ensure_ascii=False), f"schema_{e.siren or 'export'}.json", mime="application/json")
        with c2:
            # Version minifiée pour le HTML
            html_script = f'<script type="application/ld+json">\n{json.dumps(json_ld, ensure_ascii=False)}\n</script>'
            st.download_button("🌐 HTML Script", html_script, f"schema_{e.siren or 'export'}.html", mime="text/html")
        with c3:
            config = {"entity": asdict(e), "social": st.session_state.social_links}
            st.download_button("💾 Config", json.dumps(config, indent=2, ensure_ascii=False), "config.json")
        
        # Zone copie rapide
        st.text_area("📋 Copier le JSON (minifié)", json.dumps(json_ld, ensure_ascii=False), height=100)

else:
    st.info("👈 Recherche une organisation pour commencer")
    
    st.markdown(f"""
    ### v{VERSION} - JSON-LD Complet
    
    **Nouveaux champs:**
    - Logo (ImageObject)
    - Slogan
    - Noms alternatifs
    - Fondateur
    - Notes & avis (AggregateRating)
    - Recherche interne (SearchAction)
    - Zone servie
    
    **Validation:**
    - Liens vers Schema.org, Google Rich Results, WordLift
    - Validation locale intégrée
    """)

st.divider()
st.caption(f"🛡️ AAS v{VERSION} | {BUILD_ID}")
