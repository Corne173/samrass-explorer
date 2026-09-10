# Deployment validation

Validated on **10 September 2026**, using the packaged copy in a newly created Python environment. The source application and saved input files were preserved.

## Environment and dependencies

| Item | Tested version |
| --- | --- |
| Operating system | Windows, 64 bit |
| Python | 3.13.11 |
| Streamlit | 1.53.1 |
| Plotly | 6.5.2 |
| pandas | 2.3.3 |
| NumPy | 2.3.5 |

Installation from `SAMRAS/interactive_explorer/requirements.txt` succeeded in an isolated environment without access to the existing environment's installed packages. `python -m pip check` reported no broken requirements. Direct dependencies are pinned; their indirect dependencies are resolved by pip at installation time.

## Existing tests

This command was run from the packaged repository root:

```powershell
python -B -m unittest discover -s SAMRAS/interactive_explorer -p 'test_*.py'
```

**26 tests passed in 38.509 seconds, with no skipped tests.** They cover calculations, filtering, nested groups, overlaps, fixed denominators, missing values, workforce compatibility, saved data provenance, and Streamlit interface interactions.

| Saved benchmark | Verified result |
| --- | ---: |
| Records / unique record identifiers | 67,223 / 67,223 |
| Broad production areas | 24,247 |
| Explicit Stope working face | 11,912 |
| Core Tier A/B records | 123 |
| Persons injured | 59,784 |
| Persons killed | 2,180 |
| Persons disabled | 64 |
| Fatal accident records | 1,987 |
| Nonblank full narratives | 67,052 |
| Workforce commodity/year rows | 140 |

## Browser checks

The isolated environment ran Streamlit from the packaged root on a temporary localhost port. Headless Chromium loaded the live app and confirmed:

- The HTTP health endpoint returned `ok`.
- The initial metrics, four chart objects, and native dark theme loaded.
- A real mouse click on a ranked bar narrowed the record view while the reference remained 67,223.
- The Records tab displayed a complete narrative; source details could be expanded.
- Clearing the drilldown restored 24,247 production records.
- Category trend switching displayed multiple lines.
- Selecting Stope working face produced 11,912 records.
- The workforce view and annual denominator table opened.
- A 430 × 932 viewport rendered the charts without horizontal page overflow. The wide viewport was 1500 × 1050.
- No browser JavaScript errors or Streamlit exception elements were observed in the completed check.

Wide, narrow, narrow-chart, and record screenshots were visually inspected. They remain in the parent workspace's `deployment/validation/` directory, outside this repository and the source ZIP. The validation server was stopped after the check.

## Input provenance

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `samrass_consolidated_master.csv` | 61,633,584 | `22284efd9b36b83886bf58c4e20d612a2e9ed1ba334caf46f6184aec6f2a8f3e` |
| `samrass_commodity_workforce_2005_2024.md` | 61,091 | `06b6f169e7863ca165d5aefa8fa4446585d2343234eac3a40367573485d58080` |

Both inputs, the four application modules, the two existing test files, and the theme configuration match their source bytes. The original manuscript source and delivered PDF also retain their pre-preparation hashes. `SHA256SUMS.txt` lists hashes for the other deployment files; it excludes itself and Git's internal files.

## Remaining hosted checks

This validates a local Windows deployment copy. Streamlit Community Cloud's Linux environment, account permissions, deployed URL, viewer authentication, and performance with concurrent users have not yet been tested. Complete the hosted checks in [README.md](README.md) after publishing. These checks preceded GitHub publication. The package has since been published privately at [Corne173/samrass-explorer](https://github.com/Corne173/samrass-explorer). Streamlit deployment and viewer access remain to be configured.
