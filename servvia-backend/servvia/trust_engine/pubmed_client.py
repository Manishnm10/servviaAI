"""
ServVia 2. 0 - PubMed API Client
"""
import logging
import httpx
from typing import List, Dict
from xml.etree import ElementTree
import os
import asyncio

logger = logging.getLogger(__name__)


class PubMedClient:
    BASE_URL = "https://eutils.ncbi.nlm. nih.gov/entrez/eutils"
    
    def __init__(self):
        self.email = os.environ. get('PUBMED_EMAIL', 'servvia@example.com')
        self. api_key = os. environ.get('PUBMED_API_KEY', '')
    
    async def search(self, query: str, max_results: int = 10) -> List[str]:
        params = {
            'db': 'pubmed',
            'term': query,
            'retmax': max_results,
            'retmode': 'json',
            'email': self.email,
        }
        if self.api_key:
            params['api_key'] = self.api_key
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/esearch.fcgi", params=params, timeout=30. 0)
                response.raise_for_status()
                data = response.json()
                return data.get('esearchresult', {}).get('idlist', [])
        except Exception as e:
            logger.error(f"PubMed search error: {e}")
            return []
    
    async def fetch_abstracts(self, pmids: List[str]) -> List[Dict]:
        if not pmids:
            return []
        
        params = {'db': 'pubmed', 'id': ','.join(pmids), 'retmode': 'xml', 'email': self.email}
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.BASE_URL}/efetch.fcgi", params=params, timeout=30.0)
                response.raise_for_status()
                return self._parse_pubmed_xml(response.text)
        except Exception as e:
            logger.error(f"PubMed fetch error: {e}")
            return []
    
    def _parse_pubmed_xml(self, xml_text: str) -> List[Dict]:
        articles = []
        try:
            root = ElementTree.fromstring(xml_text)
            for article in root.findall('.//PubmedArticle'):
                pmid = article.findtext('. //PMID', '')
                title = article.findtext('.//ArticleTitle', '')
                abstract = article.findtext('.//AbstractText', '')
                year = article.findtext('.//PubDate/Year', '')
                pub_types = [pt.text for pt in article. findall('.//PublicationType')]
                
                articles.append({
                    'pmid': pmid,
                    'title': title,
                    'abstract': abstract[:500] if abstract else '',
                    'year': year,
                    'is_rct': any('Randomized' in str(pt) for pt in pub_types),
                    'is_meta_analysis': any('Meta-Analysis' in str(pt) for pt in pub_types),
                })
        except Exception as e:
            logger.error(f"XML parsing error: {e}")
        return articles
    
    def search_sync(self, query: str, max_results: int = 10) -> List[str]:
        return asyncio.run(self.search(query, max_results))
    
    def validate_herb_disease(self, herb: str, disease: str) -> Dict:
        query = f'"{herb}"[Title/Abstract] AND "{disease}"[Title/Abstract] AND (remedy OR treatment)'
        pmids = self.search_sync(query, max_results=5)
        
        return {
            'validated': len(pmids) > 0,
            'evidence_count': len(pmids),
            'pubmed_ids': pmids,
            'message': f'Found {len(pmids)} PubMed articles for {herb} treating {disease}'
        }
