"""Independently specified relevance judgments for retrieval evaluation.

These judgments live outside ``src/arctrellis/retrieval`` on purpose: the ranking
code must never see which fixtures or names are considered relevant. They were
written by reasoning about what a developer asking each question actually wants
from the canonical repository, not by reading ranked output.

Categories:

- ``exact``         a unique canonical symbol or route a developer would type.
- ``multi_entity``  one exact symbol name that legitimately exists several times
                    (cross-file functions, duplicate route registrations).
- ``conceptual``    multiword or architectural questions where a lexical index
                    can only match tokens, never meaning.

Every selector is a ``(kind, name, path)`` triple. Canonical UUID identities are
deliberately avoided so judgments stay readable and implementation-independent.
"""

from arctrellis.core import EntityKind
from arctrellis.retrieval.evaluation import ExpectedEntity as E
from arctrellis.retrieval.evaluation import RelevanceJudgment

JUDGMENTS: tuple[RelevanceJudgment, ...] = (
    RelevanceJudgment(
        query="PaymentService",
        category="exact",
        expected=(E(EntityKind.CLASS, "PaymentService", "payments.py"),),
        note="the only PaymentService class in the repository",
    ),
    RelevanceJudgment(
        query="stagePayment",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "stagePayment", "payments.py"),),
        note="staged mutation helper, distinct from createPayment",
    ),
    RelevanceJudgment(
        query="auditPayment",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "auditPayment", "js/app.js"),),
        note="JavaScript middleware used before the payment handler",
    ),
    RelevanceJudgment(
        query="fakePaymentWrite",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "fakePaymentWrite", "js/app.js"),),
        note="fake client function: findable, but it is not a proven database write",
    ),
    RelevanceJudgment(
        query="missingHandler",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "missingHandler", "js/app.js"),),
        note="handler with an unresolved call, still a real canonical entity",
    ),
    RelevanceJudgment(
        query="refundPayment",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "refundPayment", "ts/app.ts"),),
        note="TypeScript handler distinct from the Python createRefund",
    ),
    RelevanceJudgment(
        query="persistPaymentRoute",
        category="exact",
        expected=(E(EntityKind.FUNCTION, "persistPaymentRoute", "ts/app.ts"),),
        note="named handler behind the duplicated TypeScript registration",
    ),
    RelevanceJudgment(
        query="DELETE /payments/{paymentId}",
        category="exact",
        expected=(E(EntityKind.API_ENDPOINT, "DELETE /payments/{paymentId}", "app.py"),),
        note="the only delete route, including its dynamic parameter",
    ),
    RelevanceJudgment(
        query="listPayments",
        category="multi_entity",
        expected=(
            E(EntityKind.FUNCTION, "listPayments", "payments.py"),
            E(EntityKind.FUNCTION, "listPayments", "app.py"),
            E(EntityKind.METHOD, "listPayments", "payments.py"),
        ),
        note="the same symbol name exists as two functions and one method",
    ),
    RelevanceJudgment(
        query="createPayment",
        category="multi_entity",
        expected=(
            E(EntityKind.FUNCTION, "createPayment", "payments.py"),
            E(EntityKind.FUNCTION, "createPayment", "app.py"),
            E(EntityKind.METHOD, "createPayment", "payments.py"),
        ),
        note="reused symbol name across files and inside the service class",
    ),
    RelevanceJudgment(
        query="persistPayment",
        category="multi_entity",
        expected=(
            E(EntityKind.FUNCTION, "persistPayment", "js/service.js"),
            E(EntityKind.FUNCTION, "persistPayment", "ts/service.ts"),
        ),
        note="reused symbol name across JavaScript and TypeScript services",
    ),
    RelevanceJudgment(
        query="POST /refunds",
        category="multi_entity",
        expected=(
            E(EntityKind.API_ENDPOINT, "POST /refunds", "app.py"),
            E(EntityKind.API_ENDPOINT, "POST /refunds", "ts/app.ts"),
        ),
        note="duplicate route text registered from two languages stays distinct",
    ),
    RelevanceJudgment(
        query="GET /payments",
        category="multi_entity",
        expected=(
            E(EntityKind.API_ENDPOINT, "GET /payments", "app.py"),
            E(EntityKind.API_ENDPOINT, "GET /payments", "js/app.js"),
        ),
        note="same method and path declared by FastAPI and Express",
    ),
    RelevanceJudgment(
        query="payment creation",
        category="conceptual",
        expected=(
            E(EntityKind.FUNCTION, "createPayment", "payments.py"),
            E(EntityKind.METHOD, "createPayment", "payments.py"),
            E(EntityKind.API_ENDPOINT, "POST /payments", "app.py"),
        ),
        note="the creating symbol, its service method and the exposing endpoint",
    ),
    RelevanceJudgment(
        query="payment database write",
        category="conceptual",
        expected=(
            E(EntityKind.FUNCTION, "createPayment", "payments.py"),
            E(EntityKind.DATABASE_OPERATION, "sqlalchemy:Payment.execute@134", "payments.py"),
        ),
        note="the writer and the write-capable SQLAlchemy operation",
    ),
    RelevanceJudgment(
        query="prisma payment create",
        category="conceptual",
        expected=(
            E(EntityKind.DATABASE_OPERATION, "prisma:payment.create@127", "js/service.js"),
            E(EntityKind.DATABASE_OPERATION, "prisma:payment.create@136", "ts/service.ts"),
        ),
        note="Prisma payment write requests in both services",
    ),
    RelevanceJudgment(
        query="sqlalchemy payment",
        category="conceptual",
        expected=(
            E(EntityKind.DATABASE_OPERATION, "sqlalchemy:Payment.execute@134", "payments.py"),
            E(EntityKind.DATABASE_OPERATION, "sqlalchemy:Payment.execute@221", "payments.py"),
        ),
        note="write and read SQLAlchemy operations on the payment target",
    ),
    RelevanceJudgment(
        query="test payment",
        category="conceptual",
        expected=(
            E(EntityKind.TEST, "test_create_payment", "test_payments.py"),
            E(EntityKind.TEST, "persists a payment", "js/service.test.js"),
            E(EntityKind.TEST, "persists a payment", "ts/service.test.ts"),
        ),
        note="recognized static test entities in all three languages",
    ),
    RelevanceJudgment(
        query="payment refund endpoint",
        category="conceptual",
        expected=(E(EntityKind.API_ENDPOINT, "POST /refunds", "app.py"),),
        note="architectural question: the route that creates refunds",
    ),
    RelevanceJudgment(
        query="user validation",
        category="conceptual",
        expected=(),
        note="no user validation exists in this repository, so the query is unjudgeable",
    ),
)

#: Queries whose lexical index cannot be expected to understand the wording.
CONCEPTUAL_QUERIES = tuple(item.query for item in JUDGMENTS if item.category == "conceptual")
EXACT_QUERIES = tuple(item.query for item in JUDGMENTS if item.category == "exact")
MULTI_ENTITY_QUERIES = tuple(item.query for item in JUDGMENTS if item.category == "multi_entity")
JUDGED_QUERIES = tuple(item.query for item in JUDGMENTS if item.expected)
