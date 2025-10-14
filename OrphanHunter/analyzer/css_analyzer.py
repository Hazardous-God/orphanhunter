"""CSS analyzer for style conflicts and overlapping rules."""
import re
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
import chardet


class CSSRule:
    """Represents a CSS rule."""
    
    def __init__(self, selector: str, properties: Dict[str, str], file: str, line: int):
        self.selector = selector.strip()
        self.properties = properties  # property -> value
        self.file = file
        self.line = line
    
    def __repr__(self):
        return f"CSSRule({self.selector} in {self.file}:{self.line})"


class CSSAnalyzer:
    """Analyze CSS files for conflicts, overlaps, and usage."""
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.css_files: Dict[str, List[CSSRule]] = {}  # file -> list of rules
        self.selector_map: Dict[str, List[CSSRule]] = defaultdict(list)  # selector -> rules
        self.property_conflicts: List[Dict] = []  # List of conflicts
        self.page_css_usage: Dict[str, Set[str]] = {}  # page -> css files used
        
    def read_file_safe(self, file_path: Path) -> str:
        """Safely read file with encoding detection."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                result = chardet.detect(raw_data)
                encoding = result['encoding'] or 'utf-8'
            
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except Exception as e:
            return ""
    
    def parse_css_file(self, file_path: Path, file_key: str) -> List[CSSRule]:
        """Parse CSS file and extract rules."""
        content = self.read_file_safe(file_path)
        if not content:
            return []
        
        rules = []
        
        # Remove comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # Find all CSS rules
        # Pattern: selector { property: value; ... }
        rule_pattern = re.compile(
            r'([^{}]+)\{([^{}]+)\}',
            re.MULTILINE | re.DOTALL
        )
        
        for match in rule_pattern.finditer(content):
            selector = match.group(1).strip()
            properties_block = match.group(2).strip()
            
            # Skip @media, @keyframes, etc. for now (can be enhanced)
            if selector.startswith('@'):
                continue
            
            # Parse properties
            properties = {}
            property_pattern = re.compile(r'([a-z\-]+)\s*:\s*([^;]+);?', re.IGNORECASE)
            for prop_match in property_pattern.finditer(properties_block):
                prop_name = prop_match.group(1).strip()
                prop_value = prop_match.group(2).strip()
                properties[prop_name] = prop_value
            
            if properties:
                # Find line number
                line_num = content[:match.start()].count('\n') + 1
                rule = CSSRule(selector, properties, file_key, line_num)
                rules.append(rule)
                
                # Add to selector map
                self.selector_map[selector].append(rule)
        
        return rules
    
    def analyze_css_files(self, css_files: Dict[str, Path]):
        """Analyze all CSS files."""
        self.css_files.clear()
        self.selector_map.clear()
        
        for file_key, file_path in css_files.items():
            rules = self.parse_css_file(file_path, file_key)
            self.css_files[file_key] = rules
    
    def find_conflicts(self):
        """Find conflicting CSS rules (same selector, different properties)."""
        self.property_conflicts.clear()
        
        for selector, rules in self.selector_map.items():
            if len(rules) < 2:
                continue  # No conflict possible
            
            # Compare each pair of rules with same selector
            for i in range(len(rules)):
                for j in range(i + 1, len(rules)):
                    rule1 = rules[i]
                    rule2 = rules[j]
                    
                    # Find conflicting properties
                    conflicts = {}
                    for prop, value1 in rule1.properties.items():
                        if prop in rule2.properties:
                            value2 = rule2.properties[prop]
                            if value1 != value2:
                                conflicts[prop] = {
                                    'value1': value1,
                                    'value2': value2,
                                    'file1': rule1.file,
                                    'line1': rule1.line,
                                    'file2': rule2.file,
                                    'line2': rule2.line
                                }
                    
                    if conflicts:
                        self.property_conflicts.append({
                            'selector': selector,
                            'conflicts': conflicts,
                            'rule1': rule1,
                            'rule2': rule2
                        })
        
        return self.property_conflicts
    
    def find_duplicate_selectors(self) -> Dict[str, List[CSSRule]]:
        """Find selectors defined in multiple places."""
        duplicates = {}
        
        for selector, rules in self.selector_map.items():
            if len(rules) > 1:
                duplicates[selector] = rules
        
        return duplicates
    
    def find_overlapping_styles(self) -> List[Dict]:
        """Find styles that could be consolidated."""
        overlaps = []
        
        # Group rules by their properties
        property_groups = defaultdict(list)
        
        for file_key, rules in self.css_files.items():
            for rule in rules:
                # Create a signature of properties
                prop_sig = frozenset(rule.properties.items())
                property_groups[prop_sig].append(rule)
        
        # Find groups with multiple selectors (potential consolidation)
        for prop_sig, rules in property_groups.items():
            if len(rules) > 1:
                overlaps.append({
                    'properties': dict(prop_sig),
                    'selectors': [r.selector for r in rules],
                    'rules': rules,
                    'suggestion': 'Consider consolidating these identical styles'
                })
        
        return overlaps
    
    def scan_page_css_usage(self, page_path: Path, page_key: str) -> Set[str]:
        """Find which CSS files are used in a page."""
        content = self.read_file_safe(page_path)
        if not content:
            return set()
        
        css_files = set()
        
        # Find <link> tags for CSS
        link_pattern = re.compile(
            r'<link[^>]+href\s*=\s*[\'"]([^\'"]+\.css)[\'"]',
            re.IGNORECASE
        )
        
        for match in link_pattern.finditer(content):
            css_path = match.group(1)
            # Normalize path (simplified)
            css_path = css_path.strip().strip('/')
            css_files.add(css_path)
        
        # Find <style> tags with @import
        import_pattern = re.compile(
            r'@import\s+[\'"]([^\'"]+\.css)[\'"]',
            re.IGNORECASE
        )
        
        for match in import_pattern.finditer(content):
            css_path = match.group(1)
            css_path = css_path.strip().strip('/')
            css_files.add(css_path)
        
        self.page_css_usage[page_key] = css_files
        return css_files
    
    def analyze_page_style_conflicts(self, page_key: str) -> List[Dict]:
        """Analyze style conflicts for a specific page."""
        css_files_used = self.page_css_usage.get(page_key, set())
        
        if len(css_files_used) < 2:
            return []  # No conflicts possible with single CSS file
        
        page_conflicts = []
        
        # Check conflicts only among CSS files used in this page
        for conflict in self.property_conflicts:
            rule1_file = conflict['rule1'].file
            rule2_file = conflict['rule2'].file
            
            # Check if both conflicting files are used in this page
            if rule1_file in css_files_used and rule2_file in css_files_used:
                page_conflicts.append({
                    **conflict,
                    'page': page_key,
                    'css_files': [rule1_file, rule2_file]
                })
        
        return page_conflicts
    
    def get_statistics(self) -> Dict:
        """Get CSS analysis statistics."""
        total_rules = sum(len(rules) for rules in self.css_files.values())
        total_selectors = len(self.selector_map)
        duplicate_selectors = sum(
            1 for rules in self.selector_map.values() if len(rules) > 1
        )
        
        return {
            'total_css_files': len(self.css_files),
            'total_rules': total_rules,
            'unique_selectors': total_selectors,
            'duplicate_selectors': duplicate_selectors,
            'property_conflicts': len(self.property_conflicts),
            'pages_analyzed': len(self.page_css_usage)
        }


class StyleErrorReportGenerator:
    """Generate style error report from CSS analysis."""
    
    def __init__(self, css_analyzer: CSSAnalyzer, asset_analyzer):
        self.css_analyzer = css_analyzer
        self.asset_analyzer = asset_analyzer
    
    def generate_report(self, output_path: Path = None) -> str:
        """Generate comprehensive style error report."""
        lines = [
            "# Style Error Report",
            "",
            "## Overview",
            "",
            "Analysis of CSS conflicts, duplications, and potential optimizations.",
            ""
        ]
        
        # Statistics
        stats = self.css_analyzer.get_statistics()
        lines.extend([
            "## Statistics",
            "",
            f"- **CSS Files Analyzed**: {stats['total_css_files']}",
            f"- **Total CSS Rules**: {stats['total_rules']}",
            f"- **Unique Selectors**: {stats['unique_selectors']}",
            f"- **Duplicate Selectors**: {stats['duplicate_selectors']}",
            f"- **Property Conflicts Found**: {stats['property_conflicts']}",
            f"- **Pages Analyzed**: {stats['pages_analyzed']}",
            ""
        ])
        
        # Orphaned CSS files
        orphaned_css = self.asset_analyzer.orphaned_assets.get('.css', set())
        if orphaned_css:
            lines.extend([
                "## Orphaned CSS Files",
                "",
                f"Found {len(orphaned_css)} CSS files not referenced in any page:",
                ""
            ])
            for css_file in sorted(orphaned_css):
                lines.append(f"- `{css_file}` ⚠️ Not used in any page")
            lines.append("")
        
        # Property conflicts
        if self.css_analyzer.property_conflicts:
            lines.extend([
                "## Property Conflicts",
                "",
                "Same selector with conflicting property values:",
                ""
            ])
            
            for conflict in self.css_analyzer.property_conflicts:
                selector = conflict['selector']
                lines.extend([
                    f"### Selector: `{selector}`",
                    ""
                ])
                
                for prop, details in conflict['conflicts'].items():
                    lines.extend([
                        f"**Property**: `{prop}`",
                        "",
                        f"**Conflict:**",
                        f"- `{details['file1']}` (Line {details['line1']}): `{details['value1']}`",
                        f"- `{details['file2']}` (Line {details['line2']}): `{details['value2']}`",
                        "",
                        "**Impact**: Later-loaded CSS will override. Check load order.",
                        ""
                    ])
                
                lines.append("---")
                lines.append("")
        
        # Duplicate selectors
        duplicates = self.css_analyzer.find_duplicate_selectors()
        if duplicates:
            lines.extend([
                "## Duplicate Selectors",
                "",
                "Selectors defined in multiple locations:",
                ""
            ])
            
            for selector, rules in sorted(duplicates.items()):
                lines.extend([
                    f"### `{selector}`",
                    "",
                    f"Defined in {len(rules)} locations:",
                    ""
                ])
                
                for rule in rules:
                    props_str = ', '.join(f"{k}: {v}" for k, v in list(rule.properties.items())[:3])
                    if len(rule.properties) > 3:
                        props_str += ", ..."
                    lines.append(f"- `{rule.file}` (Line {rule.line}): {{ {props_str} }}")
                
                lines.extend([
                    "",
                    "**Suggestion**: Consider consolidating into single definition.",
                    "",
                    "---",
                    ""
                ])
        
        # Overlapping styles
        overlaps = self.css_analyzer.find_overlapping_styles()
        if overlaps:
            lines.extend([
                "## Overlapping Styles",
                "",
                "Identical style definitions that could be consolidated:",
                ""
            ])
            
            for i, overlap in enumerate(overlaps[:10], 1):  # Limit to first 10
                selectors = ', '.join(f"`{s}`" for s in overlap['selectors'][:5])
                if len(overlap['selectors']) > 5:
                    selectors += f", ... ({len(overlap['selectors']) - 5} more)"
                
                lines.extend([
                    f"### Overlap {i}",
                    "",
                    f"**Selectors**: {selectors}",
                    "",
                    "**Shared Properties**:",
                    "```css"
                ])
                
                for prop, value in list(overlap['properties'].items())[:5]:
                    lines.append(f"{prop}: {value};")
                
                lines.extend([
                    "```",
                    "",
                    "**Suggestion**: Create a shared class and apply to all elements.",
                    "",
                    "---",
                    ""
                ])
            
            if len(overlaps) > 10:
                lines.append(f"*... and {len(overlaps) - 10} more overlapping style groups*")
                lines.append("")
        
        # Page-specific conflicts
        if self.css_analyzer.page_css_usage:
            lines.extend([
                "## Page-Specific Style Conflicts",
                "",
                "CSS conflicts within individual pages:",
                ""
            ])
            
            pages_with_conflicts = 0
            for page_key in sorted(self.css_analyzer.page_css_usage.keys()):
                page_conflicts = self.css_analyzer.analyze_page_style_conflicts(page_key)
                
                if page_conflicts:
                    pages_with_conflicts += 1
                    css_files = self.css_analyzer.page_css_usage[page_key]
                    
                    lines.extend([
                        f"### Page: `{page_key}`",
                        "",
                        f"**CSS Files Used**: {len(css_files)}",
                        ""
                    ])
                    
                    for css_file in sorted(css_files):
                        lines.append(f"- `{css_file}`")
                    
                    lines.extend([
                        "",
                        f"**Conflicts**: {len(page_conflicts)}",
                        ""
                    ])
                    
                    for conflict in page_conflicts[:5]:  # Limit to first 5
                        lines.append(f"- `{conflict['selector']}` has conflicting properties")
                    
                    if len(page_conflicts) > 5:
                        lines.append(f"- ... and {len(page_conflicts) - 5} more conflicts")
                    
                    lines.extend([
                        "",
                        "---",
                        ""
                    ])
            
            if pages_with_conflicts == 0:
                lines.append("✅ No page-specific conflicts found!")
                lines.append("")
        
        # Recommendations
        lines.extend([
            "## Recommendations",
            "",
            "### High Priority",
            ""
        ])
        
        if len(orphaned_css) > 0:
            lines.append(f"1. **Remove orphaned CSS files**: {len(orphaned_css)} files not referenced")
        
        if stats['property_conflicts'] > 0:
            lines.append(f"2. **Resolve property conflicts**: {stats['property_conflicts']} conflicts found")
        
        if stats['duplicate_selectors'] > 10:
            lines.append(f"3. **Consolidate duplicate selectors**: {stats['duplicate_selectors']} selectors defined multiple times")
        
        lines.extend([
            "",
            "### Medium Priority",
            ""
        ])
        
        if len(overlaps) > 0:
            lines.append(f"1. **Consolidate overlapping styles**: {len(overlaps)} style groups with identical properties")
        
        lines.extend([
            "",
            "### Optimization Opportunities",
            "",
            "- Consider using CSS preprocessors (SASS/LESS) to manage shared styles",
            "- Implement a CSS naming convention (BEM, SMACSS)",
            "- Use CSS-in-JS for component-scoped styles",
            "- Run CSS linters (stylelint) in CI/CD pipeline",
            ""
        ])
        
        content = '\n'.join(lines)
        
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        return content

