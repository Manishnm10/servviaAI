"""
Ultimate LangChain Import Fixer V2
Handles multi-line imports and various formatting
"""

import os
import re

def fix_file(filepath):
    """Fix all LangChain imports in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes = []
        
        # Fix 1: Document Loaders (handles multi-line)
        pattern1 = r'from\s+langchain\.document_loaders\s+import'
        replacement1 = 'from langchain_community.document_loaders import'
        if re.search(pattern1, content):
            content = re.sub(pattern1, replacement1, content)
            changes.append('document_loaders')
        
        # Fix 2: Embeddings - OpenAI specific
        pattern2 = r'from\s+langchain\.embeddings\. openai\s+import'
        replacement2 = 'from langchain_community.embeddings import'
        if re.search(pattern2, content):
            content = re.sub(pattern2, replacement2, content)
            changes.append('embeddings.openai')
        
        # Fix 3: Embeddings - general
        pattern3 = r'from\s+langchain\.embeddings\s+import'
        replacement3 = 'from langchain_community.embeddings import'
        if re.search(pattern3, content):
            content = re.sub(pattern3, replacement3, content)
            changes. append('embeddings')
        
        # Fix 4: Vector Stores
        pattern4 = r'from\s+langchain\.vectorstores\. pgvector\s+import'
        replacement4 = 'from langchain_community.vectorstores. pgvector import'
        if re.search(pattern4, content):
            content = re.sub(pattern4, replacement4, content)
            changes.append('vectorstores')
        
        # Fix 5: PromptTemplate
        pattern5 = r'from\s+langchain\s+import\s+PromptTemplate'
        replacement5 = 'from langchain_core.prompts import PromptTemplate'
        if re.search(pattern5, content):
            content = re.sub(pattern5, replacement5, content)
            changes.append('PromptTemplate')
        
        # Fix 6: LLMs
        pattern6 = r'from\s+langchain\.llms\s+import'
        replacement6 = 'from langchain_community.llms import'
        if re.search(pattern6, content):
            content = re.sub(pattern6, replacement6, content)
            changes. append('llms')
        
        # Fix 7: Chat Models
        pattern7 = r'from\s+langchain\.chat_models\s+import'
        replacement7 = 'from langchain_community.chat_models import'
        if re.search(pattern7, content):
            content = re.sub(pattern7, replacement7, content)
            changes.append('chat_models')
        
        # Only write if something changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True, changes
        
        return False, []
    
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")
        return False, []

def main():
    """Find and fix all Python files"""
    print("🔍 Scanning for deprecated LangChain imports with regex.. .\n")
    
    fixed_files = []
    skipped_dirs = ['myenv', 'venv', 'env', '__pycache__', '. git', 'node_modules', 'migrations']
    
    for root, dirs, files in os.walk('. '):
        # Skip virtual environments and cache directories
        dirs[:] = [d for d in dirs if d not in skipped_dirs]
        
        for file in files:
            if file.endswith('. py'):
                filepath = os. path.join(root, file)
                was_fixed, changes = fix_file(filepath)
                
                if was_fixed:
                    fixed_files.append((filepath, changes))
                    print(f"✅ Fixed: {filepath}")
                    print(f"   Changes: {', '. join(changes)}")
    
    print(f"\n{'='*60}")
    print(f"🎉 DONE!  Fixed {len(fixed_files)} file(s)")
    print(f"{'='*60}\n")
    
    if fixed_files:
        print("📝 Summary of changes:")
        for filepath, changes in fixed_files:
            print(f"  • {filepath}: {', '.join(changes)}")
    else:
        print("✨ No deprecated imports found.  Your code is up to date!")
    
    print("\n🚀 Run 'python manage. py runserver' to verify!")

if __name__ == '__main__':
    main()