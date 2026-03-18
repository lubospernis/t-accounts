
## Balance Sheets — 2026-03-18 13:21:47

### stablecoin-issuer

| Assets | Liabilities & Equity |
|--------|----------------------|
| cash 10 | equity 10 |
| **TOTAL 10** | **TOTAL 10** ✓ |

### Payment Flow

_No transactions yet._

---

## Balance Sheets — 2026-03-18 13:58:17

### alice

| Assets | Liabilities & Equity |
|--------|----------------------|
| cash 15 |  |
|  | ***equity +15*** *(= A − L)* |
| **TOTAL 15** | **TOTAL 15** ✓ |

### bob

| Assets | Liabilities & Equity |
|--------|----------------------|
| cash 5 |  |
|  | ***equity +5*** *(= A − L)* |
| **TOTAL 5** | **TOTAL 5** ✓ |

### Payment Flow

```
bob --[cash 5]--> alice
```

---

## Balance Sheets — 2026-03-18 13:59:26

### alice

| Assets | Liabilities & Equity |
|--------|----------------------|
| cash 20 |  |
|  | ***equity +20*** *(= A − L)* |
| **TOTAL 20** | **TOTAL 20** ✓ |

### bob

| Assets | Liabilities & Equity |
|--------|----------------------|
|  |  |
|  | ***equity +0*** *(= A − L)* |
| **TOTAL 0** | **TOTAL 0** ✓ |

### Payment Flow

```
bob --[cash 5]--> alice
bob --[cash 5]--> alice
```

---
