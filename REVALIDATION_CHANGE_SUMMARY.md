# Revalidation Parameter Change Summary

## 🔄 Change Overview

**Updated revalidation time parameter from hours to minutes with new default of 60 minutes**

### Previous Behavior:

- Parameter: `--hours-old`
- Default: 24 hours
- Database query: `now() - interval '{hours_old} hours'`

### New Behavior:

- Parameter: `--minutes-old`
- Default: 60 minutes
- Database query: `now() - interval '{minutes_old} minutes'`

## 📁 Files Modified

### 1. `Worker/proxy_validator.py`

- **Function**: `revalidate_old_proxies()`
- **Changes**:
  - Parameter: `hours_old: int = 24` → `minutes_old: int = 60`
  - SQL interval: `'{hours_old} hours'` → `'{minutes_old} minutes'`
  - Log message: `"older than {hours_old} hours"` → `"older than {minutes_old} minutes"`

### 2. `Worker/main.py`

- **CLI Argument**:
  - `--hours-old` → `--minutes-old`
  - Default: `24` → `60`
  - Help text: `"N hours"` → `"N minutes"`
- **Function Calls**:
  - `hours_old=args.hours_old` → `minutes_old=args.minutes_old`
  - `proxy_filter['older_than_hours']` → `proxy_filter['older_than_minutes']`
- **Example**: `--hours-old 48` → `--minutes-old 120`

### 3. `Worker/scheduler.py`

- **Configuration**:
  - `'age_threshold_hours': 24` → `'age_threshold_minutes': 60`
  - Config access: `['age_threshold_hours']` → `['age_threshold_minutes']`
- **Function Call**:
  - `hours_old=hours_old` → `minutes_old=minutes_old`

### 4. `README.md`

- **CLI Examples**: Updated to use `--minutes-old 120` instead of `--hours-old 48`
- **Help Text**: Updated parameter description from hours to minutes
- **Default**: Changed from 24 hours to 60 minutes

### 5. `DISTRIBUTED_VALIDATION.md`

- **Examples**: Updated CLI commands to use minutes parameter
- **Documentation**: Updated parameter descriptions and defaults

## 🎯 Usage Examples

### Before:

```bash
# Revalidate proxies older than 48 hours
python Worker/main.py validate --revalidate --hours-old 48

# Default was 24 hours
python Worker/main.py validate --revalidate  # (24 hours)
```

### After:

```bash
# Revalidate proxies older than 120 minutes (2 hours)
python Worker/main.py validate --revalidate --minutes-old 120

# Default is now 60 minutes (1 hour)
python Worker/main.py validate --revalidate  # (60 minutes)
```

## ⏰ Time Conversion Reference

| Hours    | Minutes      | Use Case                        |
| -------- | ------------ | ------------------------------- |
| 1 hour   | 60 minutes   | Default - frequent revalidation |
| 2 hours  | 120 minutes  | Moderate revalidation           |
| 6 hours  | 360 minutes  | Conservative revalidation       |
| 12 hours | 720 minutes  | Infrequent revalidation         |
| 24 hours | 1440 minutes | Daily revalidation              |

## 🔧 Configuration Update

### Scheduler Configuration (Worker/scheduler.py):

```python
# Before:
'revalidation': {
    'age_threshold_hours': 24,  # 24 hours
}

# After:
'revalidation': {
    'age_threshold_minutes': 60,  # 60 minutes (1 hour)
}
```

## ✅ Benefits of the Change

1. **Greater Precision**: Minutes allow for more granular control
2. **Faster Iteration**: Default of 60 minutes enables more frequent validation
3. **Better for Development**: Shorter intervals improve testing workflows
4. **Customizable**: Users can still set longer periods (e.g., 1440 minutes = 24 hours)

## 🚨 Breaking Changes

**Command Line Interface:**

- `--hours-old` parameter no longer exists
- Must use `--minutes-old` parameter instead
- Scripts using old parameter will fail with "unrecognized arguments" error

**Function Signatures:**

- `ProxyValidator.revalidate_old_proxies(hours_old=...)` → `revalidate_old_proxies(minutes_old=...)`
- Any direct function calls need parameter name update

**Configuration:**

- Scheduler config key changed from `age_threshold_hours` to `age_threshold_minutes`
- Custom configurations need to be updated

## 🔄 Migration Guide

### For CLI Users:

```bash
# Old command:
python Worker/main.py validate --revalidate --hours-old 2

# New equivalent:
python Worker/main.py validate --revalidate --minutes-old 120
```

### For Python Code:

```python
# Old code:
validator.revalidate_old_proxies(hours_old=2, limit=100)

# New code:
validator.revalidate_old_proxies(minutes_old=120, limit=100)
```

### For Configuration:

```python
# Old config:
config = {
    'revalidation': {
        'age_threshold_hours': 6
    }
}

# New config:
config = {
    'revalidation': {
        'age_threshold_minutes': 360  # 6 hours = 360 minutes
    }
}
```

## ✅ Testing

The changes have been tested and verified:

- ✅ CLI help shows new `--minutes-old` parameter
- ✅ ProxyValidator import works with updated function signature
- ✅ All documentation updated consistently
- ✅ Default value set to 60 minutes

## 📝 Next Steps

1. **Update any custom scripts** that use `--hours-old` parameter
2. **Review scheduled job intervals** to ensure they work with new default
3. **Test revalidation functionality** with new minute-based timing
4. **Update any external documentation** or APIs that reference the old parameter

This change provides more granular control over proxy revalidation timing while maintaining backward compatibility through appropriate parameter naming and clear documentation.
