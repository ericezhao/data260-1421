# Domain Schema: Local Restaurant Inspections

## Fields

| Field | Type | Required | Purpose |
| --- | --- | --- | --- |
| `restaurantID` | Text | Yes | Primary field uniquely identifying the inspected restaurant. |
| `restaurantName` | Text | Yes | Secondary field giving the restaurant's name. |
| `Email` | Email | Yes | Email address of the submitter. |
| `Comments` | Text area | Yes | Detailed content describing observations and inspection findings. |
| `Result` | Category | Yes | Inspection result selected from the four category values below. |
| `termsAccepted` | Boolean | Yes | Records agreement to the terms and conditions. |
| `submissionDate` | ISO 8601 date-time | Generated | Date and time added by JavaScript after successful validation. |

## Category Values

The `Result` field accepts exactly one of these values:

1. `Excellent Pass`
2. `Pass`
3. `Needs Reinspection`
4. `Fail`
