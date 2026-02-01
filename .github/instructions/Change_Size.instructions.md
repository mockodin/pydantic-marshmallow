---
applyTo: '**/*.py'
---

# Change Size Management

## PR Size Guidelines

| Size | Lines Changed | Guideline |
|:-----|:-------------:|:----------|
| Small | <200 | Preferred |
| Medium | 200-500 | Acceptable |
| Large | 500-1000 | Needs justification |
| Very Large | >1000 | Split into smaller PRs |

## Decomposition Strategy for This Project

### Type Mapping Changes
- **One PR per type category**: Add all `datetime` types together, all `collection` types together
- **Include tests inline**: Type mapping + tests in same PR

### Hook/Bridge Changes
- **Separate structural changes** from feature additions
- **Test file can be separate** if change is complex

### New Ecosystem Integration
- **Integration + tests in one PR**
- **docs/README update can be separate**

## When Large PRs Are OK

- Initial project setup/bootstrap
- Major internal refactoring (if intermediate states would break tests)
- Auto-generated code (migrations, type stubs)
- Documentation overhauls

## Review Considerations

- Each PR should have **focused tests** for its changes
- Smaller PRs = easier rollbacks if issues arise
- **Prefer multiple small PRs** over one large PR with unrelated changes
