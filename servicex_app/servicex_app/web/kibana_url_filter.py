"""
Kibana URL Filter Modifier

This module provides functionality to add requestID filters to Kibana dashboard URLs.
It handles Kibana's rison-encoded state format and properly constructs filter objects.
"""

import urllib.parse
import re


def add_request_id_filter(kibana_url, request_id):
    """
    Add a requestID filter to a Kibana dashboard URL.
    
    This function parses a Kibana dashboard URL, extracts the global state (_g parameter)
    and the index pattern from existing filters, adds a new filter for the specified 
    requestID, and returns the modified URL with both the original filters and the new 
    requestID filter combined with AND logic.
    
    Args:
        kibana_url (str): Original Kibana dashboard URL containing the _g parameter
        request_id (str): Request ID value to filter by (e.g., '31f32a39-c998-4784-b8f1-3a0ef6f0bd8b')
    
    Returns:
        str: Modified URL with the requestID filter added to the filters array
        
    Raises:
        ValueError: If no index pattern can be extracted from existing filters in the URL
        
    Example:
        >>> original_url = "https://atlas-kibana.mwt2.org:5601/s/servicex/app/dashboards?..."
        >>> request_id = "31f32a39-c998-4784-b8f1-3a0ef6f0bd8b"
        >>> new_url = add_request_id_filter(original_url, request_id)
        >>> print(new_url)
        
    Notes:
        - The function preserves all existing filters and URL parameters
        - Filters are combined with AND logic (all filters must match)
        - The index pattern is extracted from existing filters in the URL
        - The _g parameter uses Kibana's rison format where:
          * () represents objects
          * !() represents arrays  
          * !n = null, !f = false, !t = true
          * Single quotes are used instead of double quotes
    """
    # Parse the URL into components
    parsed = urllib.parse.urlparse(kibana_url)
    
    # Split the fragment (hash) part which contains the dashboard path and query
    fragment_parts = parsed.fragment.split('?', 1)
    dashboard_path = fragment_parts[0]
    
    if len(fragment_parts) > 1:
        fragment_query = fragment_parts[1]
    else:
        raise ValueError("No query parameters found in URL fragment")
    
    # Parse the query parameters from the fragment
    fragment_params = urllib.parse.parse_qs(fragment_query)
    
    # Get the _g parameter (which contains the global state)
    if '_g' not in fragment_params:
        raise ValueError("No _g parameter found in URL")
    
    # Decode the _g parameter (it's URL encoded)
    _g_encoded = fragment_params['_g'][0]
    _g_decoded = urllib.parse.unquote(_g_encoded)
    
    # Extract the index pattern from existing filters
    index_pattern = _extract_index_pattern(_g_decoded)
    if not index_pattern:
        raise ValueError("Could not extract index pattern from existing filters in URL")
    
    # Create the new filter in rison format (Kibana's custom encoding format)
    # This matches the structure of existing filters in the URL
    new_filter_rison = (
        f"('$state':(store:globalState),"
        f"meta:(alias:!n,disabled:!f,index:'{index_pattern}',key:requestId,negate:!f,"
        f"params:(query:'{request_id}'),type:phrase),"
        f"query:(term:(requestID:'{request_id}')))"
    )
    
    # Find the filters array in the _g parameter
    # Filters are encoded as: filters:!(filter1,filter2,...)
    filters_start = _g_decoded.find('filters:!(')
    
    if filters_start != -1:
        # Find the matching closing parenthesis for the filters array
        # We need to track nested parentheses to find the correct closing paren
        start_pos = filters_start + len('filters:!(')
        paren_count = 1
        i = start_pos
        
        while i < len(_g_decoded) and paren_count > 0:
            if _g_decoded[i] == '(':
                paren_count += 1
            elif _g_decoded[i] == ')':
                paren_count -= 1
            i += 1
        
        end_pos = i - 1  # Position of the closing )
        
        # Extract existing filters content
        existing_filters = _g_decoded[start_pos:end_pos]
        
        # Add the new filter to the existing filters array
        if existing_filters.strip():
            new_filters_content = f"{existing_filters},{new_filter_rison}"
        else:
            new_filters_content = new_filter_rison
        
        # Build the modified _g string by replacing the filters content
        _g_modified = (
            _g_decoded[:start_pos] +
            new_filters_content +
            _g_decoded[end_pos:]
        )
    else:
        # No filters exist, add a new filters array at the beginning
        _g_modified = _g_decoded.replace(
            "(",
            f"(filters:!({new_filter_rison}),",
            1
        )
    
    # URL encode the modified _g parameter
    _g_new_encoded = urllib.parse.quote(_g_modified, safe='')
    
    # Update the fragment params with the new _g value
    fragment_params['_g'] = [_g_new_encoded]
    
    # Reconstruct the fragment query string
    # We use custom encoding to preserve the exact format
    param_parts = []
    for key, values in fragment_params.items():
        for value in values:
            param_parts.append(f"{key}={value}")
    new_fragment_query = "&".join(param_parts)
    
    # Rebuild the fragment with the dashboard path and modified query
    new_fragment = f"{dashboard_path}?{new_fragment_query}"
    
    # Reconstruct the full URL with all components
    new_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        parsed.query,
        new_fragment
    ))
    
    return new_url


def _extract_index_pattern(decoded_g_param):
    """
    Extract the index pattern ID from existing filters in the decoded _g parameter.
    
    Args:
        decoded_g_param (str): Decoded _g parameter string in rison format
        
    Returns:
        str: Index pattern ID if found, None otherwise
    """
    # Look for the pattern: index:'...'
    # This appears in the meta section of filters
    match = re.search(r"index:'([^']+)'", decoded_g_param)
    if match:
        return match.group(1)
    return None


#!/usr/bin/env python3
"""
Kibana Field Name Diagnostic Tool

This script helps you find the correct field name to use for your requestID filter.
It generates test URLs with different field name formats so you can try them in Kibana.
"""

import sys
import os


def diagnose_field_name(original_url, request_id):
    """
    Generate test URLs with different field name formats.

    Args:
        original_url: Your original Kibana URL
        request_id: The request ID value to filter by
    """
    print("="*80)
    print("KIBANA FIELD NAME DIAGNOSTIC TOOL")
    print("="*80)
    print("\nThis tool generates URLs with different field name formats.")
    print("Test each URL in Kibana to find which one shows results.\n")

    # Common field name variations
    field_names = [
        ('requestID', 'camelCase (default)'),
        ('request_id', 'snake_case'),
        ('request.id', 'nested field (dot notation)'),
        ('requestId', 'camelCase with lowercase d'),
        ('RequestID', 'PascalCase'),
        ('req_id', 'abbreviated snake_case'),
        ('reqId', 'abbreviated camelCase'),
    ]

    print(f"Request ID to filter: {request_id}\n")
    print("="*80)
    print("TEST URLS")
    print("="*80)

    for field_name, description in field_names:
        try:
            url = add_request_id_filter(original_url, request_id, field_name=field_name)
            print(f"\n{field_name} ({description}):")
            print("-"*80)
            print(url)
            print()
        except Exception as e:
            print(f"\n{field_name}: ERROR - {e}\n")

    print("\n" + "="*80)
    print("INSTRUCTIONS")
    print("="*80)
    print("""
1. Copy each URL above and paste it into your browser
2. The URL that shows results has the correct field name
3. Use that field name in your code:

    new_url = add_request_id_filter(
        original_url, 
        request_id,
        field_name='THE_CORRECT_FIELD_NAME'  # <- Replace with the working one
    )

4. If none work, you can manually check the field name:
   a. In Kibana, manually add a filter that works
   b. Copy the URL from your browser
   c. Run: python -c "from kibana_url_filter import decode_kibana_url; print(decode_kibana_url('YOUR_URL'))"
   d. Look for "key:YOUR_FIELD_NAME" in the output
    """)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python diagnose_field_name.py <kibana_url> <request_id>")
        print("\nExample:")
        print('  python diagnose_field_name.py "https://kibana.example.com/..." "31f32a39-c998-4784-b8f1-3a0ef6f0bd8b"')
        sys.exit(1)

    original_url = sys.argv[1]
    request_id = sys.argv[2]

    diagnose_field_name(original_url, request_id)
