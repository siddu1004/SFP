"""Attach skills while a message is being typed.

`live()` takes the draft so far and the state from the last call, and returns the skills to attach, the new state and
what happened. It never logs while you type; only `commit=True` (the message was sent) records a decision, so that
feedback and learning work as for any other selection.

The rules, in order:
  1. A draft with fewer than MIN_WORDS content words changes nothing ("waiting").
  2. Skills you pinned are always attached; skills you removed never are, for the rest of this message.
  3. If the draft still means what it meant when the skills were last chosen (word overlap >= SAME_TOPIC) the
     attached skills stay ("kept"): typing more words must not make the list flicker.
  4. Otherwise the hive chooses again ("updated"), and a skill that was attached before keeps its place as long as it
     is still among the best STICKY candidates, so a small change in topic moves one skill, not four.
State is plain JSON, so the editor keeps it between calls and clears it when a message is sent.
"""
import json

import sfp_hive as sel
import sfp_needs
import sfp_stack as v1

core = v1.core
MIN_WORDS = 2
SAME_TOPIC = 0.6
STICKY = 3          # how many places below the cut a previously attached skill may fall before it is dropped


def new_state():
    return {'anchor': [], 'auto': [], 'pinned': [], 'removed': []}


def content_words(text):
    return list(dict.fromkeys(t for t in core.tokens(text or '') if len(t) > 2))


def similarity(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a and b else 0.0


def _names(values):
    out = []
    for v in values or []:
        n = core.resolve_name(v)
        if n and n not in out:
            out.append(n)
    return out


def _rows(names):
    by = {s['name']: s for s in core.CATALOG['skills']}
    return [{'name': n, 'category': by[n]['category'], 'description': ' '.join(by[n]['description'].split())[:140]}
            for n in names if n in by]


def live(draft, state=None, project=None, max_skills=4, pin=(), unpin=(), remove=(), restore=(), commit=False):
    """-> {status, changed, attached:[{name, source, ...}], state, words, decision?}."""
    st = dict(new_state(), **(state or {}))
    st['pinned'] = [n for n in _names(list(st.get('pinned', [])) + list(pin)) if n not in set(_names(unpin))]
    st['removed'] = [n for n in _names(list(st.get('removed', [])) + list(remove)) if n not in set(_names(restore))]
    st['pinned'] = [n for n in st['pinned'] if n not in st['removed']]
    st['auto'] = [n for n in st.get('auto', []) if n not in st['removed'] and n not in st['pinned']]
    before = list(st['pinned']) + list(st['auto'])
    words = content_words(draft)
    decision = None

    if commit:
        import sfp_learn
        res = sfp_needs.decide(draft, project, None, (), 12000, max(max_skills, len(st['pinned'])),
                               include=st['pinned'], exclude=st['removed'])
        decision = res.get('decision')
        st['auto'] = [c['name'] for c in res['stack'] if c['name'] not in st['pinned']]
        status = 'committed'
    elif len(words) < MIN_WORDS:
        status = 'waiting'
    elif st['auto'] and similarity(words, st['anchor']) >= SAME_TOPIC:
        status = 'kept'
    else:
        room = max(max_skills - len(st['pinned']), 0)
        terms = list(sel.scan(project).get('terms', {})) if project else []
        found = sfp_needs.needs(draft, terms, exclude=st['removed'])
        res = sel.select(draft, project, None, (), 12000, max_skills + STICKY + len(found),
                         include=st['pinned'] + [n['attach'] for n in found if n['attach'] not in st['pinned']],
                         exclude=st['removed'])
        ranked = [c['name'] for c in res['stack'] if c['name'] not in st['pinned']]
        fresh = ranked[:room]
        keep = [n for n in st['auto'] if n in ranked[:room + STICKY]]
        auto = keep[:room]
        auto += [n for n in fresh if n not in auto][:room - len(auto)]
        st['auto'] = auto
        st['anchor'] = words
        status = 'updated'

    attached = list(st['pinned']) + list(st['auto'])
    source = {n: 'pinned' for n in st['pinned']}
    rows = [dict(r, source=source.get(r['name'], 'auto')) for r in _rows(attached)]
    out = {'status': status, 'changed': attached != before, 'attached': rows, 'state': st, 'words': words}
    out['needs'] = sfp_needs.needs(draft, exclude=st['removed']) if status != 'waiting' else []
    if decision:
        out['decision'] = decision
    return out


def format_live(res):
    head = '%s%s' % (res['status'], ' (changed)' if res['changed'] else '')
    return '\n'.join([head] + ['  %-34s %s' % (r['name'], r['source']) for r in res['attached']])
