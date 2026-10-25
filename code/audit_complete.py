#!/usr/bin/env python3
"""Independent read-only false-COMPLETE audit.

For every row the solution reports as ``COMPLETE``, search all participant
evidence captured at or before that case's ``audit_at`` for the subject's
current and historical direct identifiers (exact email, verified email hash,
phone, stable user reference). Every hit is then classified:

* ``accounted`` — some emitted verification step addresses the same resource;
* ``state_conflict`` — a step addresses the resource but its asserted state
  disagrees with the latest observation of that resource at the cutoff;
* ``unaccounted`` — the subject's identifier appears on a resource that no step
  addresses, i.e. a possible surviving copy behind a COMPLETE claim.

Matching is token-exact. ``user_42`` must never match ``user_428``; names are
never treated as links. This script never edits ``output.csv``, never edits the
dataset and never changes audit logic. It exists to falsify our own completions.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ghost_audit.ingest import EvidenceStore  # noqa: E402
from ghost_audit.identity import IdentityIndex, normalize_email  # noqa: E402
from ghost_audit.schema import HEADER, AuditError, read_csv, timestamp  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

CITED_STATES = {
    'ABSENT': {'ABSENT'},
    'PRESENT': {'PRESENT', 'FOUND'},
    'REDACTED': {'REDACTED'},
    'ANONYMIZED': {'ANONYMIZED'},
    'DISABLED': {'DISABLED'},
    'BLOCKED': {'BLOCKED'},
}


def digits(value):
    return re.sub(r'\D', '', str(value or ''))


def text_of(observation):
    """Locator plus flattened properties, lowercased, for literal identifier search."""
    parts = [observation.locator, observation.resource, observation.system, observation.category]
    stack = [observation.properties]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set)):
            stack.extend(item)
        elif isinstance(item, (str, int, float)):
            parts.append(str(item))
    return ' '.join(p for p in parts if p).lower()


def matcher(kind, value):
    """Compile a token-exact search for one subject identifier value."""
    value = str(value)
    if kind == 'user_id':
        return re.compile(rf'(?<!\w){re.escape(value)}(?!\d)')
    if kind == 'phone':
        compact = digits(value)
        if len(compact) < 7:
            return None
        return re.compile(rf'(?<!\d){compact}(?!\d)')
    if kind == 'email_hash':
        return re.compile(rf'(?<![0-9a-f]){re.escape(value.lower())}(?![0-9a-f])')
    # Email: require non-address characters on both sides.
    return re.compile(rf'(?<![\w@.+-]){re.escape(value.lower())}(?![\w@.+-])')


def subject_matchers(index, uid, cutoff):
    aliases = index.aliases(uid, cutoff)
    matchers = []
    for kind, values in (('email', [normalize_email(v) for v in aliases['email']]),
                         ('email_hash', [v.strip().lower() for v in aliases['email_hash']]),
                         ('phone', aliases['phone']),
                         ('user_id', [uid])):
        for value in values:
            compiled = matcher(kind, value)
            if compiled is not None:
                matchers.append((kind, value, compiled))
    return aliases, matchers


def hits_in(observation, matchers):
    text = text_of(observation)
    compact = None
    found = set()
    for kind, value, compiled in matchers:
        target = text
        if kind == 'phone':
            compact = compact if compact is not None else digits(text)
            target = compact
        if compiled.search(target):
            found.add((kind, value))
    return found


def audit(dataset, output, report, only=None, verbose=False):
    store = EvidenceStore(dataset, images=False)
    index = IdentityIndex(read_csv(dataset / 'user_identities.csv'), read_csv(dataset / 'user_audit_log.csv'))
    requests = {r['case_id']: r for r in read_csv(dataset / 'deletion_requests.csv')}
    with output.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or []) != HEADER:
            raise AuditError('Unexpected output header')
        rows = list(reader)

    complete = [r for r in rows if r['deletion_status'] == 'COMPLETE']
    if only:
        complete = [r for r in complete if r['case_id'] in only]

    results = []
    for row in complete:
        case_id = row['case_id']
        request = requests.get(case_id)
        entry = {'case_id': case_id, 'subject': None, 'steps': 0, 'evidence_inspected': 0,
                 'accounted': 0, 'unaccounted': [], 'state_conflicts': [],
                 'after_cutoff_observation': [], 'status': 'ok'}
        if request is None:
            entry['status'] = 'missing request row'
            results.append(entry)
            continue
        try:
            cutoff = timestamp(request['audit_at'])
            uid = index.resolve(request['email'], cutoff, request['requested_at'])
        except AuditError as error:
            entry['status'] = f'identity not resolvable: {error}'
            results.append(entry)
            continue
        entry['subject'] = uid
        aliases, matchers = subject_matchers(index, uid, cutoff)
        entry['identifier_counts'] = {'email': len(aliases['email']), 'email_hash': len(aliases['email_hash']),
                                      'phone': len(aliases['phone'])}

        steps = json.loads(row['steps_json'])
        entry['steps'] = len(steps)
        step_state = {}
        for step in steps:
            step_state.setdefault(step['resource_id'], set()).add(step['state'])

        # Latest observation per resource *observed* at or before the cutoff, used for
        # state conflicts. A capture made at the cutoff can contain a row whose own
        # recorded_at is later; that future state must not be used as fact at audit_at.
        latest = {}
        for observation in store.observations:
            if not observation.eligible(cutoff):
                continue
            key = observation.resource
            rank = (timestamp(observation.observed_at), timestamp(observation.captured_at))
            if key not in latest or rank > latest[key][0]:
                latest[key] = (rank, observation)

        seen = set()
        for observation in store.observations:
            if timestamp(observation.captured_at) > cutoff:
                continue
            entry['evidence_inspected'] += 1
            hits = hits_in(observation, matchers)
            if not hits:
                continue
            identity = (observation.evidence_id, observation.resource, observation.state, observation.observed_at)
            if identity in seen:
                continue
            seen.add(identity)
            if not observation.eligible(cutoff):
                # Captured by the cutoff but its own timestamp is later: it cannot
                # establish the state at audit_at, so it is reported separately
                # rather than counted as a defect.
                entry['after_cutoff_observation'].append({
                    'evidence_id': observation.evidence_id, 'resource': observation.resource,
                    'category': observation.category, 'state': observation.state,
                    'observed_at': observation.observed_at, 'captured_at': observation.captured_at,
                    'matched': sorted(f'{k}:{v}' for k, v in hits)})
                continue
            if observation.resource in step_state:
                entry['accounted'] += 1
                current = latest.get(observation.resource)
                if current:
                    asserted = step_state[observation.resource]
                    allowed = set().union(*(CITED_STATES.get(state, set()) for state in asserted))
                    if current[1].state not in allowed:
                        entry['state_conflicts'].append({
                            'evidence_id': observation.evidence_id,
                            'resource': observation.resource,
                            'step_states': sorted(asserted),
                            'latest_state': current[1].state,
                            'latest_evidence': current[1].evidence_id,
                            'latest_observed_at': current[1].observed_at,
                            'matched': sorted(f'{k}:{v}' for k, v in hits),
                        })
                continue
            entry['unaccounted'].append({
                'evidence_id': observation.evidence_id,
                'path': observation.path,
                'captured_at': observation.captured_at,
                'observed_at': observation.observed_at,
                'system': observation.system,
                'resource': observation.resource,
                'category': observation.category,
                'state': observation.state,
                'matched': sorted(f'{k}:{v}' for k, v in hits),
            })
        if entry['unaccounted']:
            entry['status'] = 'UNACCOUNTED HITS'
        elif entry['state_conflicts']:
            entry['status'] = 'STATE CONFLICT'
        results.append(entry)

    summary = {
        'output': str(output),
        'complete_rows_audited': len(complete),
        'rows_with_unaccounted_hits': sum(1 for e in results if e['unaccounted']),
        'rows_with_state_conflicts': sum(1 for e in results if e['state_conflicts']),
        'after_cutoff_observations': sum(len(e.get('after_cutoff_observation', [])) for e in results),
        'unaccounted_hits': sum(len(e['unaccounted']) for e in results),
        'state_conflicts': sum(len(e['state_conflicts']) for e in results),
        'accounted_hits': sum(e['accounted'] for e in results),
        'identity_failures': sum(1 for e in results if e['status'].startswith('identity')),
        'by_category': dict(Counter(h['category'] for e in results for h in e['unaccounted'])),
        'by_system': dict(Counter(h['system'] for e in results for h in e['unaccounted'])),
        'by_evidence': dict(Counter(h['evidence_id'] for e in results for h in e['unaccounted'])),
        'cases': results,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')

    print(f"COMPLETE rows audited:          {summary['complete_rows_audited']}")
    print(f"Rows with unaccounted hits:     {summary['rows_with_unaccounted_hits']}")
    print(f"Unaccounted subject-linked hits:{summary['unaccounted_hits']:>4}")
    print(f"Rows with state conflicts:      {summary['rows_with_state_conflicts']}")
    print(f"State conflicts:                {summary['state_conflicts']}")
    print(f"Accounted subject-linked hits:  {summary['accounted_hits']}")
    print(f"Identity resolution failures:   {summary['identity_failures']}")
    print(f"Captured-but-observed-later:    {summary['after_cutoff_observations']}  (excluded: future state)")
    if summary['by_category']:
        print(f"By category: {summary['by_category']}")
        print(f"By system:   {summary['by_system']}")
        print(f"Top evidence: {sorted(summary['by_evidence'].items(), key=lambda kv: -kv[1])[:8]}")
    for entry in results:
        if not entry['unaccounted'] and not entry['state_conflicts']:
            continue
        print(f"\n{entry['case_id']} ({entry['subject']}) {entry['steps']} steps: "
              f"{len(entry['unaccounted'])} unaccounted, {len(entry['state_conflicts'])} state conflict(s)")
        for hit in (entry['unaccounted'] + entry['state_conflicts'])[:100 if verbose else 10]:
            print('  ' + json.dumps(hit, sort_keys=True))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset')
    parser.add_argument('--output', type=Path, default=ROOT / 'output.csv')
    parser.add_argument('--report', type=Path, default=ROOT / 'evaluation_runs/false_complete_audit.json')
    parser.add_argument('--case', action='append', help='Restrict to specific case IDs (repeatable)')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    summary = audit(args.dataset, args.output, args.report, set(args.case) if args.case else None, args.verbose)
    return 1 if (summary['unaccounted_hits'] or summary['state_conflicts']) else 0


if __name__ == '__main__':
    sys.exit(main())
