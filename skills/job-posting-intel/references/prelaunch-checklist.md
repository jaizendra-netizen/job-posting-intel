# Campaign pre-launch checklist (LinkedIn senders and cold-email sequencers)

No campaign starts until every item passes. Verify by reading the data back from the platform
API, never by "the write returned OK". Never sample: scan every lead.

## A. Message content (every lead)
1. **Final literal text only.** Zero spintax `{a|b}`, zero unresolved variables, zero placeholder
   tokens (`[FirstName]`, `<YOUR_PRODUCT>`), zero merge or SQL debris. Run
   `scripts/validate_messages.py` over the exact text you will upload.
2. **Names clean.** No emoji or credentials in the greeting ("Matt Lee, CISSP" becomes "Matt"),
   diacritics transliterated (María becomes Maria, never Mara), honorifics dropped, greeting name
   equals the row's name.
3. **No unintended links.** Clients auto-link bare domains. Write the company as a word in
   signatures; include only links you deliberately approved.
4. **No tracking leaks.** Never mention that someone liked, viewed, visited or engaged. Signals
   choose the topic and the timing; they never appear in the copy.

## B. Sender match
5. Every account's messages are voiced and signed as that account's human. When two senders share
   a lead pool, keep per-sender message variants and point each campaign at its own variant.
6. Fallback messages match their branch (no "thanks for connecting" on an already-connected
   branch) and their sender.
7. Email signature: sender's name + verified title + company as a word. Exactly one signature per
   message: if the sequencer auto-appends one, remove the inline sign-off. LinkedIn messages need
   no signature (the sender's name and photo are already shown).
8. Capability match: InMail steps only on accounts that can send InMail; check sender auth status
   at launch.

## C. List hygiene
9. Channel exclusivity proven by query: no lead in both the email and LinkedIn campaign unless
   intended, no lead under two senders without the platform's cross-campaign exclusion turned on.
10. Already-contacted and in-conversation people are excluded or routed to a continuation message.
11. Email lists: check the MX of every domain. Send only to mail hosted on mainstream providers you
    have tested deliverability against; route domains behind strict secure email gateways to
    LinkedIn instead.
12. Upload reconcile: platform lead count equals intended count, and custom fields are present when
    you READ a lead back. Some add-lead calls report success while adding nothing: diff the missing
    leads by profile slug (URL-decoded) and re-add.

## D. Delivery settings
13. Schedule in the recipient's time zone, on agreed days; no weekend email unless agreed.
14. Email: plain text, open and click tracking off, stop on reply on, conservative per-mailbox daily
    cap (OneGTMLab's own rule is 15 or fewer per mailbox per day).

## E. Test before live
15. Send one test per sender persona to internal inboxes and one real LinkedIn message or
    connection request to a team-owned profile. Look at what actually arrives: variable bugs are
    invisible in the editor and obvious in the delivered message.
16. Never edit bodies while a campaign runs: pause, edit, read back, resume. After a live fix,
    confirm no lead received the pre-fix version.

## F. Platform syntax traps (verify on your own account)
- Variable syntax differs by platform. HeyReach uses single braces (`{FIRST_NAME}`); double braces
  ship literally. Smartlead uses double braces. Never assume syntax transfers; trust a rendered test
  over API-doc examples.
- HeyReach build order: create empty list, add leads (with per-lead custom fields), create the
  campaign (the list id field is `linkedInUserListId`), then set the sequence. Leads bind at launch.
- HeyReach sequence delays: every node after an action node needs a delay of at least 3 hours.
- HeyReach launch is a CLI command (`heyreach campaigns start --id <id>`), not a REST call. A 404 on
  a guessed endpoint is evidence about the guess, not about the platform.
- HeyReach custom-field shapes differ: list writes use `{name, value}`, campaign writes use
  `{fieldName, fieldValue}`. Read back before concluding an upload failed.
- When reading an API key from `.env`, split on the first `=` only; base64 keys end in `=` padding
  and `cut -d= -f2` truncates them into a 401.

## G. Approval
17. Nothing goes live, and nothing live is paused, edited or resumed, without the user's explicit
    go for that specific action.
