---
name: Parallel search request
about: Run checkpointed restoration searches in Actions
title: '[search] Restoration experiment'
---
Use a title beginning with `[search]`. OWNER/MEMBER/COLLABORATOR issues trigger jobs.

```json
{"candidates":["horse-5d","horse-6c"],"seconds":60,"nodes":200000}
```

To resume an earlier artifact, add `"resume_run":123456789` with its run ID.
