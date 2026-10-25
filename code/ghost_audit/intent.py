"""Clause-scoped multilingual authorization, with explicit ambiguity failures."""
import re
from dataclasses import dataclass
from .schema import AuditError

@dataclass
class Intent:
    authorized: bool
    reason: str
    prerequisites: tuple = ()

DELETE=r'delet|eras|remov|clos(?:e|ed|ing|ure)|profile is gone|profile was gone|elimin|borr|apag|exclu|suppr|effac|削除|消去|삭제'
OBJECT=r'account|profile|personal|identit|records|details|data|everything|all (?:my )?(?:data|records|information)|cuenta|datos|compte|donn[eé]es|conta|dados|アカウント|個人情報|계정|개인정보|search result|export file|addresses|integration|analytics'
ACCOUNT=r'account|profile|personal|cuenta|compte|conta|アカウント|個人情報|계정|개인정보'
RETAINED=r'invoice|audit record|legal|retain|factur|fatura|obligato|security record'
NEGATION=(r"\b(?:do not|don't|never|refrain from|avoid)\b"
    r"|\bnot\s+(?:(?:a\s+)?request\w*|asking|authoriz\w*|consent\w*)"
    r"|\b(?:should|must|would|could|can|may|might)(?:n't| not)\b[^.;]*\b(?:delet|eras|remov|clos)"
    r"|\b(?:didn't|doesn't|isn't|aren't|wasn't|weren't|wouldn't|couldn't|shouldn't|mustn't)\b"
    r"|\bnot\s+be\s+(?:deleted|removed|erased|closed)\b"
    r"|\bunder\s+no\s+circumstances\b"
    r"|\bwithout\s+(?:delet|remov)"
    r"|\bno\s+(?:quiero|solicito|elim\w*|borr\w*|apag\w*|remov\w*)"
    r"|\bnão\s+(?:quero|solicito|exclu\w*|apag\w*|elim\w*|remov\w*)"
    r"|\bne\b[^.;]*\bpas\b|n'effacez pas|削除しない|消去しない|삭제하지")

def classify(text):
    t=text.strip().casefold().replace('’',"'")
    if re.search(r'^(?:how (?:do|can|would)|what (?:happens|would happen)|why (?:would|should|do|did))\b',t):
        return Intent(False,'Hypothetical/instructions request; no present authorization')
    if re.search(r'^(?:(?:should|shall|must|may|might|can|could|would)\s+i|(?:is|would)\s+it\s+(?:possible|okay|allowed|fine)|(?:do|should)\s+i\s+(?:need|have))\b',t):
        return Intent(False,'Advice/hypothetical question; no present authorization')
    if re.search(r'\b(?:maybe|might|considering|thinking about|may)\b[^.!?]*(?:delet|eras|clos)',t):
        raise AuditError('Ambiguous intent: no definite present deletion authorization')
    conditional=re.search(r'(?:\bif\b[^.!?]*[,;][^.!?]*(?:delet|eras|clos)|(?:delet|eras|clos)[^.!?]*\bonly if\b|\bunless\b)',t)
    retained_unless=re.search(r'\bunless\b',t) and re.search(RETAINED,t) and not re.search(r'\bif\b',t)
    if conditional and not retained_unless:
        raise AuditError('Conditional authorization needs evidence of condition fulfillment')
    clauses=re.split(r'[;\n]|[.!?](?:\s|$)|,?\s+\b(?:but|however|mais|pero|mas)\b\s*',t)
    positive=False;veto=False;negative=False
    for clause in clauses:
        deletion=bool(re.search(DELETE,clause))
        negated=bool(re.search(NEGATION,clause))
        keep_account=bool(re.search(r'(?:keep|leave)\b[^.;]*\b(?:account|profile)\b[^.;]*(?:active|as it is|in place)',clause))
        if keep_account:veto=True
        marketing_only=bool(re.search(r'(?:marketing|mailing|promotional).*(?:only|still want|keep my)',clause))
        if deletion and negated:
            negative=True
            # Negating destruction of policy-retained content does not negate
            # a separate account-deletion clause. Mixed/unclear scopes fail closed.
            if re.search(ACCOUNT,clause) or not re.search(RETAINED,clause):veto=True
            continue
        if marketing_only:continue
        if deletion and re.search(OBJECT,clause):positive=True
        if re.search(r'finish the deletion|complete the deletion|handle them and disable',clause):positive=True
    if positive and veto:raise AuditError('Conflicting deletion and preservation instructions require review')
    if positive:
        # A copy/export mentioned as a prerequisite is not a self-contained
        # export request; it gates destructive action. An explicit statement that
        # the copy was already received does not create a new prerequisite.
        copy_request=re.search(r'\b(?:send|give|provide|email|mail|need|want|wish|like|request|obtain|get)\b[^.!?]*\b(?:copy|export|download|portable)\b',t)
        data_export=re.search(r'\b(?:export|download)\b[^.!?]*\b(?:my|of my)\b[^.!?]*\b(?:data|records|information|account|profile)\b',t)
        wants_copy=copy_request or data_export
        confirmation_copy=re.search(r'\b(?:confirmation|acknowledg(?:e)?ment|receipt|completion)\b[^.!?]*\bcopy\b|\bcopy\s+of\s+(?:the\s+)?(?:confirmation|acknowledg(?:e)?ment|receipt|completion)\b',t)
        already=re.search(r'\b(?:already|previously)\b[^.!?]*\b(?:downloaded|received|exported)\b|\b(?:have|had)\b[^.!?]*\b(?:downloaded|received|exported)\b',t)
        declined=re.search(r"\b(?:don't|do not|no)\b[^.!?]*\b(?:need|want)\b[^.!?]*\b(?:copy|export|download)\b",t)
        pre=('export',) if wants_copy and not confirmation_copy and not already and not declined else ()
        return Intent(True,'Authorized deletion/audit; retained-record exceptions preserve policy',pre)
    if negative or veto:return Intent(False,'Deletion withheld or account explicitly preserved')
    if re.search(r'copy|download|export|correct|change|update|amend|rectif|access|provide|portable|mailing|unsubscribe|marketing|promotional|reset|information request|out of date|information\b[^.!?]*\b(?:hold|about me|on me)|\b(?:what|which)\b[^.!?]*\b(?:data|information)\b[^.!?]*\b(?:hold|store)\b|更新|訂正|수정|copia|corrig',t):
        return Intent(False,'Access/correction/export/marketing request')
    raise AuditError('Unrecognized request intent requires semantic review')
