# Compatibility Analysis Instructions

This document provides systematic guidance for analyzing and validating compatibility when Marshmallow or Pydantic releases new features.

## When to Run Compatibility Analysis

1. **Marshmallow releases a new version** (check https://github.com/marshmallow-code/marshmallow/releases)
2. **Pydantic releases a new version** (check https://github.com/pydantic/pydantic/releases)
3. **Before any major release** of pydantic-marshmallow
4. **When adding new bridge features**

---

## Step 1: Gather Release Information

### For Marshmallow Updates

```bash
# Check current installed version
pip show marshmallow

# Check latest version
pip index versions marshmallow

# Review changelog
# https://marshmallow.readthedocs.io/en/stable/changelog.html
```

**Key areas to review:**
- New Schema methods or parameters
- New field types
- New Meta options
- Hook changes (pre_load, post_load, pre_dump, post_dump)
- Validation changes
- Error handling changes
- Deprecations

### For Pydantic Updates

```bash
# Check current installed version
pip show pydantic

# Check latest version
pip index versions pydantic

# Review changelog
# https://docs.pydantic.dev/latest/changelog/
```

**Key areas to review:**
- New ConfigDict options
- New Field() parameters
- New validator decorators or modes
- New type annotations
- Serialization changes (model_dump, model_dump_json)
- Validation changes (model_validate, model_validate_json)
- Error structure changes
- Deprecations

---

## Step 2: Update Capability Matrix

After reviewing changelogs, update the capability matrix below:

1. Add new features to the appropriate section
2. Mark initial status as ❌ (not yet supported)
3. Assess implementation complexity
4. Prioritize based on user impact

---

## Step 3: Write Compatibility Tests

For each new feature, create tests in `tests/test_compatibility.py`:

### Test Template

```python
class TestMarshmallow_X_Y_Features:
    """Tests for Marshmallow X.Y new features."""

    def test_new_feature_name(self):
        """Test [feature description].

        Added in: Marshmallow X.Y
        Docs: [URL]
        """
        # Arrange
        class TestModel(BaseModel):
            field: str

        schema = schema_for(TestModel)()

        # Act
        result = schema.load({"field": "value"})

        # Assert
        assert result.field == "value"


class TestPydantic_X_Y_Features:
    """Tests for Pydantic X.Y new features."""

    def test_new_feature_name(self):
        """Test [feature description].

        Added in: Pydantic X.Y
        Docs: [URL]
        """
        # Test implementation
        pass
```

---

## Step 4: Run Full Test Suite

```bash
# Run all tests with verbose output
pytest tests/ -v --tb=long

# Run with coverage
pytest tests/ --cov=pydantic_marshmallow --cov-report=term-missing --cov-report=html

# Run specific compatibility tests
pytest tests/test_compatibility.py -v
```

---

## Step 5: Analyze Failures

### Failure Categories

1. **Breaking Change**: Existing functionality no longer works
   - Priority: CRITICAL
   - Action: Fix immediately before release

2. **New Feature Gap**: New upstream feature not supported
   - Priority: Based on user impact
   - Action: Add to backlog, implement as needed

3. **Deprecation Warning**: Using deprecated API
   - Priority: MEDIUM
   - Action: Update to new API before it's removed

4. **Behavioral Change**: Same API, different behavior
   - Priority: HIGH
   - Action: Document and adapt

### Failure Analysis Template

```markdown
## [Feature Name] - [Marshmallow/Pydantic] X.Y

**Status**: ❌ Failing / ⚠️ Warning / ✅ Passing

**Type**: Breaking Change / New Feature / Deprecation / Behavioral Change

**Description**:
[What changed and how it affects the bridge]

**Error Message**:
```
[Paste error]
```

**Root Cause**:
[Why this is happening]

**Fix Required**:
[What needs to change in bridge.py]

**Test**:
```python
def test_feature():
    # Minimal reproduction
    pass
```
```

---

## Step 6: Implement Fixes

### For Bridge Architecture Changes

Update `src/pydantic_marshmallow/bridge.py`:

1. **Hook ordering**: Modify `_do_load()` method
2. **New Meta options**: Update `PydanticSchema.Meta` class
3. **Field mapping**: Update `_type_to_marshmallow_field()` method
4. **Validation**: Update `_validate_with_pydantic()` method
5. **Serialization**: Update `dump()` method

### For New Feature Support

1. Add implementation to bridge.py or type_mapping.py
2. Add tests to appropriate test file
3. Update capability matrix status below to ✅
4. Update README.md if user-facing

---

## Step 7: Validate Ecosystem Compatibility

Test with ecosystem tools:

```python
# tests/test_ecosystem.py

def test_flask_rebar_compatibility():
    """Verify flask-rebar still works."""
    # Mock or real test
    pass

def test_webargs_compatibility():
    """Verify webargs still works."""
    pass

def test_apispec_compatibility():
    """Verify apispec still works."""
    pass
```

---

## Step 8: Document Changes

### Update Files

1. **README.md**: Update if APIs changed
2. **This file**: Update capability matrix status
3. **pyproject.toml**: Update version and dependencies

### Release Notes

When releasing, create GitHub Release notes with:
- **Added**: New features and type support
- **Changed**: Minimum version requirements
- **Fixed**: Compatibility fixes
- **Deprecated**: Deprecated APIs (with migration path)

---

## Automated Compatibility Checks

### GitHub Actions Workflow

Create `.github/workflows/compatibility.yml`:

```yaml
name: Compatibility Check

on:
  schedule:
    - cron: '0 0 * * 1'  # Weekly on Monday
  workflow_dispatch:

jobs:
  check-versions:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        marshmallow: ['3.18', '3.19', '3.20', '3.21', 'latest']
        pydantic: ['2.0', '2.5', '2.6', '2.7', 'latest']

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
          pip install "marshmallow==${{ matrix.marshmallow }}" "pydantic==${{ matrix.pydantic }}"

      - name: Run tests
        run: pytest tests/ -v
```

---

## Quick Reference: API Locations

### Marshmallow APIs We Use

| API | Location | Our Usage |
|:----|:---------|:----------|
| `Schema` | `marshmallow.Schema` | Base class |
| `fields.*` | `marshmallow.fields` | Field mapping |
| `pre_load` | `marshmallow.decorators` | Hook support |
| `post_load` | `marshmallow.decorators` | Hook support |
| `pre_dump` | `marshmallow.decorators` | Hook support |
| `post_dump` | `marshmallow.decorators` | Hook support |
| `ValidationError` | `marshmallow.exceptions` | Error handling |
| `RAISE/EXCLUDE/INCLUDE` | `marshmallow` | Unknown handling |
| `_invoke_load_processors` | `Schema` (internal) | Hook ordering |
| `_do_load` | `Schema` (internal) | Load override |

### Pydantic APIs We Use

| API | Location | Our Usage |
|:----|:---------|:----------|
| `BaseModel` | `pydantic` | Model class |
| `ConfigDict` | `pydantic` | Model config |
| `Field` | `pydantic` | Field options |
| `ValidationError` | `pydantic` | Error handling |
| `model_validate` | `BaseModel` | Validation |
| `model_dump` | `BaseModel` | Serialization |
| `model_fields` | `BaseModel` | Field introspection |
| `field_validator` | `pydantic` | Custom validation |
| `model_validator` | `pydantic` | Model validation |
| `PydanticUndefined` | `pydantic_core` | Default detection |

---

## Version Compatibility Matrix

Update this when testing new versions:

| pydantic-marshmallow | Marshmallow | Pydantic | Python | Status |
|:---------------------|:------------|:---------|:-------|:------:|
| 0.1.x | 3.18+ | 2.0+ | 3.9-3.14 | ✅ |

**CI tests against:** Python 3.9, 3.10, 3.11, 3.12, 3.13, 3.14 on Ubuntu/Windows/macOS

---

## Checklist for New Version Compatibility

- [ ] Review Marshmallow changelog
- [ ] Review Pydantic changelog
- [ ] Update [CAPABILITY_MATRIX.md](/CAPABILITY_MATRIX.md) with new features
- [ ] Write tests for new features
- [ ] Run full test suite
- [ ] Analyze and fix failures
- [ ] Test ecosystem tools
- [ ] Update documentation
- [ ] Update version constraints in pyproject.toml
- [ ] Create PR with changes

---

## Feature Capability Matrix

**See [CAPABILITY_MATRIX.md](/CAPABILITY_MATRIX.md) in the project root for the complete capability matrix.**

The matrix documents:
- All Marshmallow features → Bridge support status
- All Pydantic features → Available via bridge
- Type mappings (Pydantic → Marshmallow fields)
- Ecosystem tool compatibility
- Version compatibility

**Test Suite**: 375+ tests | **Tested Versions**: Marshmallow 3.x, Pydantic 2.x

### Quick Reference: Key Features

| Category | Status |
|:---------|:------:|
| Hook ordering (@pre_load → Pydantic → @post_load) | ✅ |
| All Marshmallow field types | ✅ |
| All Pydantic validators | ✅ |
| Partial loading | ✅ |
| Unknown field handling (RAISE/EXCLUDE/INCLUDE) | ✅ |
| Error format conversion | ✅ |
| Ecosystem tools (Flask-Rebar, webargs, apispec, etc.) | ✅ |

```