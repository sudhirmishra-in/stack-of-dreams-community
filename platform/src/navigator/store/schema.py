"""DynamoDB table definitions (the SAM template mirrors these; tests create tables from them).

DATA TABLE: single-table design, on-demand billing.
  Access patterns -> keys
   AP1 get one resource + its inventory .......... PK=RES#<id>, SK=META | INV#<item>      (one Query)
   AP2 list a namespace ordered by ZIP ........... GSI1: gsi1pk=NS#<real|demo>, gsi1sk=Z#<zip>#<id>
   AP3 cross-source duplicate lookup ............. GSI2: gsi2pk=FP#<fingerprint>
   AP4 sync state / run history per source ....... PK=SYNC#<source>, SK=STATE | RUN#<iso>   (RUN has TTL)
   AP5 citywide activity by program/period ....... PK=ACT#<source>#<program>, SK=P#<periodEnd>
   AP6 ZIP geocode cache (centroids never change)  PK=ZIP#<zip>, SK=GEO
  Pilot scale (hundreds to low thousands of items) makes a namespace Query + app-side filtering cheaper
  and simpler than per-type indexes; revisit if the directory grows past ~10k items.

USAGE TABLE: hot counters isolated from the data table (separate IAM, TTL, blast radius).
   Daily/monthly/global counters ... PK=U#<sub>#D#<date> | U#<sub>#M#<month> | G#D#<date>, SK=CTR   (TTL)
   In-flight concurrency lock ...... PK=U#<sub>, SK=INFLIGHT (expiresAt; conditional write)
   Reservation / idempotency ....... PK=REQ#<idempotency key>, SK=R   (TTL)
   User profile (admin overrides) .. PK=USER#<sub>, SK=PROFILE
   Global config (quotas, switch) .. PK=CONFIG, SK=QUOTAS | SWITCH
"""

DATA_TABLE_DEF = {
    "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
    "AttributeDefinitions": [
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
        {"AttributeName": "gsi1pk", "AttributeType": "S"},
        {"AttributeName": "gsi1sk", "AttributeType": "S"},
        {"AttributeName": "gsi2pk", "AttributeType": "S"},
        {"AttributeName": "gsi2sk", "AttributeType": "S"},
    ],
    "GlobalSecondaryIndexes": [
        {
            "IndexName": "gsi1",
            "KeySchema": [{"AttributeName": "gsi1pk", "KeyType": "HASH"}, {"AttributeName": "gsi1sk", "KeyType": "RANGE"}],
            "Projection": {"ProjectionType": "ALL"},
        },
        {
            "IndexName": "gsi2",
            "KeySchema": [{"AttributeName": "gsi2pk", "KeyType": "HASH"}, {"AttributeName": "gsi2sk", "KeyType": "RANGE"}],
            "Projection": {"ProjectionType": "KEYS_ONLY"},
        },
    ],
    "BillingMode": "PAY_PER_REQUEST",
}

USAGE_TABLE_DEF = {
    "KeySchema": [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
    "AttributeDefinitions": [
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
    ],
    "BillingMode": "PAY_PER_REQUEST",
}
