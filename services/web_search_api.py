#!/usr/bin/env python3
"""
Web Search API Service
Integrates with web search services (currently uses mock/fallback)
"""

import logging
from typing import Dict, List, Optional
import random
from datetime import datetime
from services.service_base import SearchService, ServiceResponse

logger = logging.getLogger("WebSearchAPI")


class MockWebSearchAPI(SearchService):
    """Mock web search API for development"""

    def __init__(self):
        """Initialize mock search service"""
        self._connected = False

        # Mock search results database
        self.mock_results = {
            'climate change': [
                {'url': 'https://climate.nasa.gov', 'title': 'NASA Climate', 'snippet': 'Climate science...',
                 'credibility': 0.95},
                {'url': 'https://www.ipcc.ch', 'title': 'IPCC Report', 'snippet': 'Climate change impacts...',
                 'credibility': 0.98},
                {'url': 'https://example-blog.com', 'title': 'Climate Blog', 'snippet': 'My thoughts...',
                 'credibility': 0.3},
            ],
            'python programming': [
                {'url': 'https://python.org', 'title': 'Python.org', 'snippet': 'Official Python site...',
                 'credibility': 0.99},
                {'url': 'https://docs.python.org', 'title': 'Python Docs', 'snippet': 'Documentation...',
                 'credibility': 0.95},
                {'url': 'https://random-tutorial.com', 'title': 'Python Tutorial', 'snippet': 'Learn Python...',
                 'credibility': 0.45},
            ],
            'artificial intelligence': [
                {'url': 'https://openai.com', 'title': 'OpenAI', 'snippet': 'AI research...',
                 'credibility': 0.90},
                {'url': 'https://arxiv.org', 'title': 'ArXiv', 'snippet': 'Research papers...',
                 'credibility': 0.95},
                {'url': 'https://ai-clickbait.com', 'title': 'AI Hype', 'snippet': 'AI will...',
                 'credibility': 0.2},
            ],
        }

        # Source credibility database
        self.source_credibility = {
            'nasa.gov': 0.98,
            'python.org': 0.99,
            'ipcc.ch': 0.98,
            'arxiv.org': 0.96,
            'docs.python.org': 0.95,
            'openai.com': 0.92,
            'github.com': 0.90,
            'example-blog.com': 0.30,
            'ai-clickbait.com': 0.20,
        }

    def connect(self) -> bool:
        """Connect to service"""
        self._connected = True
        logger.info("Connected to Mock Web Search API")
        return True

    def disconnect(self) -> bool:
        """Disconnect from service"""
        self._connected = False
        logger.info("Disconnected from Mock Web Search API")
        return True

    def is_connected(self) -> bool:
        """Check connection status"""
        return self._connected

    def search(self, query: str) -> ServiceResponse:
        """
        Perform a web search

        Args:
            query: Search query string

        Returns:
            ServiceResponse with search results
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        try:
            # Check if we have mock results for this query
            query_lower = query.lower()

            results = None
            for key, value in self.mock_results.items():
                if key in query_lower:
                    results = value
                    break

            # If no exact match, generate mock results
            if not results:
                results = [
                    {
                        'url': f'https://example{i}.com/result{i}',
                        'title': f'Result {i} for "{query}"',
                        'snippet': f'This is a search result about {query}...',
                        'credibility': random.uniform(0.3, 0.9)
                    }
                    for i in range(3)
                ]

            return ServiceResponse(
                success=True,
                data={
                    'query': query,
                    'results': results,
                    'num_results': len(results),
                },
                metadata={'service': 'web_search', 'timestamp': datetime.now().isoformat()}
            )

        except Exception as e:
            return ServiceResponse(success=False, error=str(e))

    def get_source_credibility(self, url: str) -> ServiceResponse:
        """
        Get credibility score for a source

        Args:
            url: URL to assess

        Returns:
            ServiceResponse with credibility score (0-1)
        """
        if not self._connected:
            return ServiceResponse(success=False, error="Not connected to service")

        try:
            # Extract domain
            domain = url.replace('https://', '').replace('http://', '').split('/')[0]

            # Look up credibility
            credibility = self.source_credibility.get(domain)

            if credibility is None:
                # Estimate based on domain characteristics
                if 'gov' in domain or 'edu' in domain or 'org' in domain:
                    credibility = random.uniform(0.7, 0.95)
                elif 'com' in domain:
                    credibility = random.uniform(0.3, 0.85)
                else:
                    credibility = random.uniform(0.2, 0.6)

            return ServiceResponse(
                success=True,
                data={
                    'url': url,
                    'domain': domain,
                    'credibility': credibility,
                    'rating': self._rate_credibility(credibility),
                },
                metadata={'service': 'credibility_check', 'timestamp': datetime.now().isoformat()}
            )

        except Exception as e:
            return ServiceResponse(success=False, error=str(e))

    def _rate_credibility(self, score: float) -> str:
        """Convert credibility score to rating"""
        if score >= 0.9:
            return 'Highly Credible'
        elif score >= 0.7:
            return 'Credible'
        elif score >= 0.5:
            return 'Moderately Credible'
        else:
            return 'Low Credibility'


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Test the service
    service = MockWebSearchAPI()
    service.connect()

    # Test search
    result = service.search('climate change')
    print(f"Search results: {result.data['num_results']} found")
    for res in result.data['results']:
        print(f"  - {res['title']}")

    # Test credibility
    result = service.get_source_credibility('https://nasa.gov/article')
    print(f"\nCredibility: {result.data}")

    service.disconnect()
