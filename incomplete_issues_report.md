# ServiceX Incomplete Issue Descriptions Report

Generated: 2025-11-29

## Summary
Found **27 issues** with incomplete or inadequate descriptions out of 46 total open issues reviewed.

---

## Critical: No Description Provided (3 issues)

### #1208 - Improve local dev mounts
- **Status:** Draft PR
- **Problem:** NO description provided at all
- **Recommendation:** Add description explaining what mounts need improvement and why

### #1183 - Logstash for DID finders
- **Status:** Draft PR
- **Problem:** No actual description, just noted as "addressing DID finder logging configuration"
- **Recommendation:** Explain the logging configuration changes being made

### #1167 - DID Finder Cache should expire after a week
- **Problem:** Referenced by issue #1211 but no body content shown
- **Recommendation:** Add description with rationale for one-week expiration

---

## High Priority: Single Sentence Descriptions (8 issues)

### #1217 - Trigger data lifecycle job only at top of relevant hour
- **Current:** "Modifies cron specification to prevent triggering on every minute"
- **Missing:** Current cron spec, desired cron spec, which job is affected

### #1215 - Fix logout on OIDC
- **Current:** Brief mention of "Globus auth's non-compliance"
- **Missing:** Specific parameters involved, error messages, actual fix approach

### #497 - Remove "messages" from DB
- **Current:** "Transform_result has 'messages' that is always set to 0"
- **Missing:** Why it was added originally, migration strategy, impact analysis

### #435 - release_helm_chart.sh Changes Tag for Memcached Container
- **Current:** "Script incorrectly updates Rucio DID Finder's memcached image tag"
- **Missing:** Current behavior, expected behavior, proposed solution

### #386 - Make the Integration Tested Branch Obvious in Run Log
- **Current:** "We need to be clear what version of the Service is being tested"
- **Missing:** Where in logs, what format, implementation approach

### #333 - Add title to servicex web pages
- **Current:** User story only
- **Missing:** Which pages, title format, implementation details

### #325 - CERN Open DID Finder failed error message needs the dataset identifier
- **Current:** "Error messages lack dataset identifiers"
- **Missing:** Example error messages, where to add identifier, format

### #1210 - Job to kill stuck transformers
- **Current:** Two sentences about transformers hanging and periodic shutdown
- **Missing:** How to detect "stuck", what timeout to use, implementation specifics

---

## Medium Priority: Vague or Missing Technical Details (16 issues)

### #1184 - Enable DID Finder logging to LogStash
- **Problem:** Author admits "unclear if configuration-related"
- **Missing:** Investigation results, root cause, proposed solution

### #1168 - Xrootd file open failure causes fallback to next replica
- **Problem:** Author states mechanism is "poorly understood" with "only anecdotal evidence"
- **Missing:** Reproduction steps, expected vs actual behavior, investigation needed

### #429 - Systematic Variations From xAOD Files
- **Current:** User story only
- **Missing:** Technical approach, data format, API design

### #428 - Front ServiceX with Columnar Cache
- **Current:** User story only
- **Missing:** Cache technology, invalidation strategy, architecture

### #414 - Hung transformer should be terminated
- **Current:** Problem statement about hanging transformers
- **Missing:** Detection mechanism, timeout values, notification approach

### #377 - A Reference Guide for Documentation
- **Current:** Request for auto-generated reference docs
- **Missing:** Which functions to document, tool to use, structure

### #370 - Small site contributing to ServiceX
- **Current:** Vague requirements from user perspective
- **Missing:** Specific resource constraints, deployment model, success criteria

### #347 - ServiceX Status Page
- **Current:** One sentence user story
- **Missing:** What metrics to show, technology choice, where to host

### #342 - ServiceX Transform DID Finder
- **Current:** "I want to chain transforms together"
- **Missing:** Use cases, data flow, API design

### #341 - Unzip Transformer
- **Current:** Has some detail but lacks specification
- **Missing:** Supported compression formats, error handling, performance requirements

### #332 - CodeGen error for xAOD is not reported back to user
- **Current:** Problem stated (errors don't surface)
- **Missing:** Current error flow, proposed error propagation, UI changes

### #317 - Report error when transform fails during initialization
- **Current:** "Misconfigured transforms fail silently"
- **Missing:** Examples of misconfigurations, detection method, error reporting mechanism

### #314 - Transform UUID as a DOI
- **Current:** One sentence user story
- **Missing:** DOI provider, registration process, metadata requirements

### #293 - Option to Fail Transform if a Single File Fails
- **Current:** One sentence user story
- **Missing:** API design, backwards compatibility, configuration approach

### #484 - Filter Transforms by Number of Events
- **Current:** "I want to restrict a dataset by the number of input events"
- **Missing:** API design, implementation approach, sampling strategy

### #321 - Support of OIDC tokens for ServiceX
- **Current:** Brief request for OIDC support
- **Missing:** Which OIDC provider, token validation approach, integration points

---

## Recommendations by Issue Type

### For Draft PRs (#1208, #1183)
- Add description before converting to full PR
- Explain what changes are being made and why
- Include testing approach

### For Bug Reports (#1168, #332, #325, #317, #435)
- Add reproduction steps
- Include error messages/logs
- Describe expected vs actual behavior
- Propose solution approach

### For Feature Requests (#429, #428, #414, #377, #370, #347, #342, #341, #314, #293, #484, #321)
- Expand user story with acceptance criteria
- Add technical approach/architecture
- Include API design or configuration changes
- Consider backwards compatibility
- Define success metrics

### For Maintenance Tasks (#1217, #1215, #1210, #497, #386, #333, #1184, #1167)
- Explain the "why" - what problem does this solve?
- Provide before/after examples
- Include migration/deployment considerations
- Add testing approach

---

## Overall Patterns Observed

1. **User stories without acceptance criteria:** Many issues are just one-line user stories without technical details
2. **Missing investigation results:** Several issues note uncertainty ("unclear", "poorly understood") without follow-up investigation
3. **No implementation approach:** Feature requests often lack any proposed solution
4. **Missing examples:** Issues would benefit from concrete examples, error messages, or use cases
5. **Draft PRs without descriptions:** PRs are opened without explaining the changes

## Suggested Process Improvements

1. Use issue templates that require:
   - Problem statement
   - Current behavior vs desired behavior
   - Proposed solution (even if tentative)
   - Acceptance criteria
   - Testing approach

2. Label issues needing more information with "needs-detail" tag

3. Require investigation results before accepting "unclear" issues

4. For draft PRs, require description before review
