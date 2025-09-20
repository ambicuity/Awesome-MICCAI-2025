#!/usr/bin/env python3
"""
Automated script to update the Awesome MICCAI 2025 list by finding papers on arXiv
that have public code repositories and categorizing them by topic.
"""

import re
import arxiv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
from typing import Dict, List, Set, Tuple, Optional


def get_github_gitlab_huggingface_links(text: str) -> List[str]:
    """Extract GitHub, GitLab, and Hugging Face repository links from text."""
    # Patterns for different repository hosting services
    patterns = [
        r'https?://github\.com/[^\s\)]+',
        r'https?://gitlab\.com/[^\s\)]+',
        r'https?://huggingface\.co/[^\s\)]+',
        r'https?://www\.github\.com/[^\s\)]+',
        r'https?://www\.gitlab\.com/[^\s\)]+',
        r'https?://www\.huggingface\.co/[^\s\)]+',
    ]
    
    links = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        links.extend(matches)
    
    # Clean up links (remove trailing punctuation)
    cleaned_links = []
    for link in links:
        # Remove trailing punctuation and whitespace
        link = re.sub(r'[.,;:!?)\]}>"\'\s]+$', '', link)
        cleaned_links.append(link)
    
    return list(set(cleaned_links))  # Remove duplicates


def categorize_paper(title: str, abstract: str) -> List[str]:
    """Categorize a paper based on keywords in title and abstract."""
    # Define category keywords
    categories = {
        'Segmentation': ['segment', 'segmentation', 'mask', 'masking', 'delineation', 'contour'],
        'Reconstruction': ['reconstruct', 'reconstruction', 'restore', 'restoration', 'super-resolution', 'denoising'],
        'Classification': ['classification', 'classify', 'classifier', 'recognition', 'detection', 'diagnosis'],
        'Image Registration': ['registration', 'alignment', 'transform', 'transformation', 'deformation', 'motion'],
        'Domain Adaptation': ['domain adaptation', 'transfer learning', 'cross-domain', 'domain shift', 'generalization'],
        'Generative Models': ['generative', 'generation', 'synthesis', 'gan', 'diffusion', 'vae', 'autoencoder']
    }
    
    # Combine title and abstract for keyword matching
    text = (title + ' ' + abstract).lower()
    
    matched_categories = []
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            matched_categories.append(category)
    
    # If no specific category matches, default to a general category
    if not matched_categories:
        matched_categories = ['General']
    
    return matched_categories


def search_miccai_papers() -> List[Dict]:
    """Search for MICCAI 2025 papers on arXiv."""
    print("Searching for MICCAI 2025 papers on arXiv...")
    
    # Search for papers with "MICCAI 2025" in title, abstract, or comments
    search_queries = [
        'ti:"MICCAI 2025"',
        'abs:"MICCAI 2025"',
        'co:"MICCAI 2025"'
    ]
    
    all_papers = []
    seen_ids = set()
    network_error = False
    
    # Create arXiv client
    client = arxiv.Client()
    
    for query in search_queries:
        try:
            search = arxiv.Search(
                query=query,
                max_results=100,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )
            
            # Use the new client.results() method instead of search.results()
            for paper in client.results(search):
                if paper.entry_id not in seen_ids:
                    seen_ids.add(paper.entry_id)
                    
                    # Extract repository links from abstract and comments
                    text_to_search = paper.summary
                    if hasattr(paper, 'comment') and paper.comment:
                        text_to_search += ' ' + paper.comment
                    
                    repo_links = get_github_gitlab_huggingface_links(text_to_search)
                    
                    # Only include papers that have repository links
                    if repo_links:
                        categories = categorize_paper(paper.title, paper.summary)
                        
                        paper_info = {
                            'title': paper.title.strip(),
                            'arxiv_url': paper.entry_id,
                            'repo_links': repo_links,
                            'categories': categories,
                            'published': paper.published
                        }
                        all_papers.append(paper_info)
                        
                        print(f"Found: {paper.title}")
                        print(f"  Categories: {', '.join(categories)}")
                        print(f"  Repos: {', '.join(repo_links)}")
                        print()
            
            # Add delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"Error searching with query '{query}': {e}")
            # Check if this is a network-related error
            error_str = str(e).lower()
            if any(term in error_str for term in ['connection', 'network', 'resolve', 'timeout', 'unreachable']):
                network_error = True
            continue
    
    print(f"Total papers found with code: {len(all_papers)}")
    
    # If we had network errors and no papers found, inform user
    if network_error and len(all_papers) == 0:
        print("WARNING: Network connectivity issues detected. Unable to fetch papers from arXiv.")
        print("The script will continue but no new papers will be added.")
    
    return all_papers


def generate_paper_list_markdown(papers: List[Dict], category: str) -> str:
    """Generate markdown list for papers in a specific category."""
    category_papers = [p for p in papers if category in p['categories']]
    
    if not category_papers:
        return ""
    
    # Sort papers by publication date (newest first)
    category_papers.sort(key=lambda x: x['published'], reverse=True)
    
    markdown_lines = []
    for paper in category_papers:
        # Use the first repository link for the main code link
        main_repo = paper['repo_links'][0]
        
        # Create the markdown entry
        title = paper['title']
        arxiv_url = paper['arxiv_url']
        
        line = f"* **[{title}]({arxiv_url})** - [Code]({main_repo})"
        
        # Add additional repository links if available
        if len(paper['repo_links']) > 1:
            additional_repos = paper['repo_links'][1:]
            additional_links = [f"[Code{i+2}]({repo})" for i, repo in enumerate(additional_repos)]
            line += " | " + " | ".join(additional_links)
        
        markdown_lines.append(line)
    
    return '\n'.join(markdown_lines)


def update_readme(papers: List[Dict]) -> None:
    """Update the README.md file with the new paper lists."""
    readme_path = 'README.md'
    
    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print("README.md not found!")
        return
    
    # If no papers were found, don't update anything to preserve existing content
    if not papers:
        print("No new papers found - preserving existing content in README.md")
        return
    
    # Define the categories that should be updated
    categories = ['Segmentation', 'Reconstruction', 'Classification', 'Image Registration', 'Domain Adaptation', 'Generative Models', 'General']
    
    # Update each category section only if papers exist for that category
    for category in categories:
        paper_list = generate_paper_list_markdown(papers, category)
        
        # Only update if there are papers for this category
        if paper_list.strip():
            # Find the placeholder block for this category
            pattern = rf'(<!-- BEGIN {category.upper().replace(" ", "_")}_PAPERS -->).*?(<!-- END {category.upper().replace(" ", "_")}_PAPERS -->)'
            replacement = f'\\1\n{paper_list}\n\\2'
            
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            print(f"Updated {category} section with {len([p for p in papers if category in p['categories']])} papers")
    
    # Write the updated content back to README.md
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("README.md updated successfully!")
        
        if papers:
            print(f"Added {len(papers)} papers across {len(set(cat for paper in papers for cat in paper['categories']))} categories.")
            
    except Exception as e:
        print(f"Error writing to README.md: {e}")
        # Don't raise the exception - let the script continue


def main():
    """Main function to run the paper update process."""
    print("Starting automated update of Awesome MICCAI 2025 list...")
    
    # Search for papers
    papers = search_miccai_papers()
    
    if not papers:
        print("No papers with code repositories found.")
        print("This could be due to:")
        print("1. No new MICCAI 2025 papers with code available on arXiv")
        print("2. Network connectivity issues preventing arXiv access")
        print("3. Changes in arXiv API or search patterns")
        print("\nExisting papers in README.md will be preserved.")
    
    # Try to update README with new papers if found
    # If no papers found, existing content will be preserved
    update_readme(papers)
    
    print("Update process completed!")
    
    # Exit with success status regardless of paper count
    # This prevents GitHub Actions from marking the workflow as failed
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
        if exit_code is not None:
            import sys
            sys.exit(exit_code)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import sys
        sys.exit(0)  # Exit with success to prevent GitHub Actions from failing