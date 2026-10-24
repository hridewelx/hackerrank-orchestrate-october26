"""Conservative multilingual authorization baseline with explicit unresolved conditions."""
import re
from dataclasses import dataclass
from .schema import AuditError

@dataclass
class Intent:
    authorized: bool
    reason: str
    prerequisites: tuple = ()

def classify(text):
    t=text.casefold().replace('’',"'")
    if re.search(r'^(?:how (?:do|can|would)|what (?:happens|would happen))\b',t):return Intent(False,'Hypothetical or instructions request, no present authorization')
    if re.search(r'(?:marketing|mailing|promotional).*(?:only|still want|keep my)|remove me from marketing lists only',t):return Intent(False,'Marketing opt-out only')
    negation=r"do not (?:delete|erase|close)|don't (?:delete|erase|close)|not (?:a request to erase|asking for deletion)|without (?:deleting|removing)|no (?:elimines|borres)|ne supprimez pas|削除しない|삭제하지"
    if re.search(negation,t): return Intent(False,'Explicitly withholds deletion authorization')
    if re.search(r'(?:\bif\b[^.!?]*[,;][^.!?]*(?:delet|eras|clos)|(?:delet|eras|clos)[^.!?]*\bonly if\b|\bunless\b)',t):
        # Conditions are not silently treated as satisfied. Conditional cleanup after
        # checking whether records remain is itself an authorized investigation.
        raise AuditError('Conditional authorization needs evidence of condition fulfillment')
    delete=r'delet|eras|remov|clos(?:e|ed|ing|ure)|profile is gone|profile was gone|elimin|suppr|exclus[aã]o|削除|삭제'
    object_=r'account|profile|personal|identit|records|details|cuenta|compte|conta|アカウント|계정|search result|export file|addresses|integration|analytics'
    if re.search(delete,t) and re.search(object_,t):
        pre=('export',) if re.search(r'export.*(?:then|before).*delet',t) else ()
        return Intent(True,'Explicit deletion or audit of a prior deletion',pre)
    if re.search(r'finish the deletion|complete the deletion|handle them and disable',t): return Intent(True,'Completion of prior deletion')
    if re.search(r'copy|download|export|correct|change|marketing|promotional|reset|information request|out of date|更新|訂正|수정|copia|corrig',t):
        return Intent(False,'Access/correction/export/marketing request')
    raise AuditError('Unrecognized request intent requires semantic review')
