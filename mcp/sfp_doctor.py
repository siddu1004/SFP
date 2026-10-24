"""One command that checks the whole hive end to end and says what is wrong: `sfp_hive.py doctor`.

Each check is small and independent, runs against the real catalog, and reports ok / warn / fail with a one-line
detail and, when it is not ok, what to do. Nothing is changed and no model is called. The editor runs the same checks
(`doctor --json`) and shows them as a list, so "is it connected?" has one answer.
"""
import json
import os
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def _timed(fn):
    t = time.time()
    out = fn()
    return out, int((time.time() - t) * 1000)


def checks(router_port=8787, project=None):
    import sfp_hive as sel
    import sfp_learn
    import sfp_library
    import sfp_live
    import sfp_needs
    import sfp_route
    import sfp_stack as v1
    out = []

    def add(name, status, detail, fix=''):
        out.append({'name': name, 'status': status, 'detail': detail, 'fix': fix})

    add('Python', 'ok' if sys.version_info >= (3, 8) else 'fail', sys.version.split()[0], 'Install Python 3.8 or newer.')
    skills = len(v1.core.CATALOG['skills'])
    add('Catalog', 'ok' if skills > 500 else 'fail', '%d skills' % skills, 'Run python3 scripts/sync.py.')
    try:
        key_ok = json.load(open(os.path.join(ROOT, 'index.json'), encoding='utf-8')).get('key') == v1.core.index_key()
        add('Search index', 'ok' if key_ok else 'warn', 'fresh' if key_ok else 'stale', 'Run python3 scripts/sync.py.')
    except (OSError, ValueError):
        add('Search index', 'warn', 'index.json missing or unreadable', 'Run python3 scripts/sync.py.')

    d = sfp_learn.data_dir()
    try:
        os.makedirs(d, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=d):
            pass
        add('Data folder', 'ok', d)
    except OSError as e:
        add('Data folder', 'fail', '%s: %s' % (d, e.strerror), 'Set SFP_DATA_DIR to a folder you can write to.')

    try:
        res, ms = _timed(lambda: sel.select('add tests for the checkout form', project, max_skills=3))
        add('Selection', 'ok' if res['stack'] and ms < 1500 else 'warn', '%d skills in %d ms' % (len(res['stack']), ms),
            'Selection is slow or empty: run python3 mcp/sfp_hive.py evaluate.')
    except Exception as e:  # noqa: BLE001 - a diagnostic reports, it does not raise
        add('Selection', 'fail', '%s: %s' % (type(e).__name__, e))

    try:
        r, ms = _timed(lambda: sfp_live.live('make the signup form accessible and keyboard friendly'))
        names = [a['name'] for a in r['attached']]
        add('Live attaching', 'ok' if names else 'fail', '%d skills in %d ms%s' % (len(names), ms, ', bundle ' + r['bundles'][0]['id'] if r.get('bundles') else ''))
    except Exception as e:  # noqa: BLE001
        add('Live attaching', 'fail', '%s: %s' % (type(e).__name__, e))

    try:
        found, ms = _timed(lambda: sfp_needs.needs('turn this photo into a 3d model'))
        add('Needs', 'ok' if found and found[0]['id'] == 'make-3d' else 'fail', '%s in %d ms' % (found[0]['id'] if found else 'nothing found', ms))
    except Exception as e:  # noqa: BLE001
        add('Needs', 'fail', '%s: %s' % (type(e).__name__, e))

    try:
        lib, ms = _timed(sfp_library.library)
        ok = lib['counts']['skills'] == skills and lib['families'] and lib['bundles']
        add('Skill library', 'ok' if ok else 'fail', '%d areas, %d bundles, %d clusters in %d ms' % (
            len(lib['families']), len(lib['bundles']), len(lib['clusters']), ms))
    except Exception as e:  # noqa: BLE001
        add('Skill library', 'fail', '%s: %s' % (type(e).__name__, e))

    cfg = sfp_route.load_config()
    models = sum(len(p.get('models', [])) for p in cfg.get('providers', []))
    local = sfp_route.discover(timeout=0.4)
    n_local = sum(len(f['models']) for f in local)
    add('Local models', 'ok' if n_local else 'warn', ', '.join('%s (%d)' % (f['name'], len(f['models'])) for f in local) or 'none found',
        'Start Ollama or LM Studio, or ignore this if you only use cloud models.')
    add('Router config', 'ok' if models else 'warn', '%d models in routes.json' % models, 'Run python3 mcp/sfp_route.py setup --yes.')
    try:
        with urllib.request.urlopen('http://127.0.0.1:%d/health' % router_port, timeout=0.6) as r:
            health = json.loads(r.read())
        ready = sum(1 for m in health['models'] if m['state'] == 'ready')
        add('Router running', 'ok' if ready else 'warn', '%d of %d models ready' % (ready, len(health['models'])),
            'Every model is cooling down or missing its key: see python3 mcp/sfp_route.py status.')
    except (OSError, ValueError):
        add('Router running', 'warn', 'not running on port %d' % router_port, 'Start it: python3 mcp/sfp_route.py serve.')

    try:
        import sfp_mcp
        add('MCP server', 'ok', 'version %s, %d tools' % (sfp_mcp.SERVER_VERSION, len(getattr(sfp_mcp, 'TOOLS', []) or [])) if hasattr(sfp_mcp, 'TOOLS') else 'version %s' % sfp_mcp.SERVER_VERSION)
    except Exception as e:  # noqa: BLE001
        add('MCP server', 'fail', '%s: %s' % (type(e).__name__, e))
    return out


def summary(items):
    worst = 'ok'
    for c in items:
        if c['status'] == 'fail':
            return 'fail'
        if c['status'] == 'warn':
            worst = 'warn'
    return worst


def format_checks(items):
    mark = {'ok': 'ok  ', 'warn': 'WARN', 'fail': 'FAIL'}
    lines = []
    for c in items:
        lines.append('%s  %-16s %s' % (mark[c['status']], c['name'], c['detail']))
        if c['status'] != 'ok' and c['fix']:
            lines.append('      -> ' + c['fix'])
    lines.append('')
    lines.append({'ok': 'Everything is connected.', 'warn': 'Working, with things to look at.', 'fail': 'Something is broken.'}[summary(items)])
    return '\n'.join(lines)
