print("Starting markdown test...")

import markdown

# Test markdown content
test_md = '''
# Test Header

## Subheader

This is some **bold** text and *italic* text.

- List item 1
- List item 2

1. Ordered item 1
2. Ordered item 2

[Link text](https://example.com)

```python
def test():
    print('Hello world')
```

> Blockquote
'''

# Convert markdown to HTML using the library
try:
    extensions = [
        'markdown.extensions.extra',
        'markdown.extensions.codehilite',
        'markdown.extensions.smarty',
        'markdown.extensions.nl2br',
        'markdown.extensions.toc'
    ]
    html = markdown.markdown(test_md, extensions=extensions)
    print('Conversion successful!')
    print('-' * 40)
    print(html)
except Exception as e:
    print(f'Conversion failed: {e}') 