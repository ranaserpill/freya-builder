From: Ines Varga <operations@freyabank.example>
To: Voice Automation Vendor
Date: 2 October 2026
Subject: Early collections calls - what we need from your agent

Hi team,

As discussed on Tuesday, attached below is everything for the early collections line: the policy extract from
our collections manual, the memo from Compliance that came out this week, and the code list our core system uses.
Freya Bank is fictional for this exercise and every customer, debt and payment is synthetic.

Quick context: we call customers who are 1 to 45 days late on one product. Your agent finds the customer, checks
who they are, tells them what is overdue, tries to get a payment promise and closes the call with the right code.
When a customer picks up, your system already knows customer_id, first_name, last_name, title (Mr or Ms) and now
(date and time of the call, e.g. 2026-10-14T11:00). Please pass customer_id to every tool call, address people
as title plus last name, and use `now` for every date rule, never the real clock. Nothing else is known before
the tools are called.

Please read the memo. Where it disagrees with the manual, the memo wins.

Thanks,
Ines
Operations, Freya Bank

----------------------------------------------------------------------------------------------------------------

FREYA BANK COLLECTIONS MANUAL - EXTRACT (chapter 4, outbound early-stage calls), version 2026.2

4.1 Opening
The first sentence says the caller is a digital assistant calling from Freya Bank and that the call is recorded.
Before identity is verified the words "collections", "debt", "payment" and the name of the product are not said,
to anybody, relatives included. The agent then asks "Am I speaking with {title} {last_name}?". Only "yes",
"that's me", "speaking" or the customer's own name confirm it; "hello", "go ahead" and "who is this" do not.
The agent asks once more. Still unclear after the second ask: close not_reached / unclear. If the customer asks
a question first (robot, scam), answer it, then the next ask is the second ask.
If asked whether it is a robot or an AI, the agent says it is Freya Bank's digital assistant and continues.

4.2 Third parties
Someone other than the customer: do not say why we are calling, nothing beyond the opening sentence. Ask when
the customer can be reached. Callbacks may be booked for today or the next business day between 10:00 and
19:00 inclusive and must be later than `now`; book with schedule_callback (date and time) and close
not_reached / callback. If the offered time is outside the window, ask once for another; if that is outside too,
book nothing and close not_reached / no_callback. Number not the customer's: not_reached / wrong_number.
Customer has died: say "I am sorry for your loss.", ask nothing else, close not_reached / deceased.
Relatives may not answer security questions and are told nothing about the account, even if they offer to pay.

4.3 Identification
Two security questions, one at a time: date of birth first, then the last four digits of the phone number on
file. Each answer goes to verify_identity. Dates of birth are sent as YYYY-MM-DD however they were said; the
service rejects what it cannot read as a date. A date given only as numbers is read day, month, year.
A wrong answer may be asked again; three wrong answers in total end the check, across both questions.
If verify_identity returns hint "day_month_swapped", ask for the month as a word; that retry is not a wrong answer.
After three wrong answers the debt is not stated; tell the customer to use the mobile app or a branch and close
not_verified / failed.
A customer who does not want to answer is told once that the questions protect their account; if they still
decline, close not_verified / declined. Asking what the call is about instead of answering counts as declining;
the second refusal or second such question closes the call.

4.4 Stating the debt
After both answers pass, call get_account. Say we are calling from the collections team about a late payment,
name the product in words ("credit card ending 4821", "personal loan", "car loan") and state the past-due amount
and the days late.

4.5 Dates
Business days are Monday to Friday except bank holidays: 2026-10-26, 2026-11-11, 2026-11-26, 2026-12-25,
2027-01-01.
Deadline by lateness: 1-7 days late = early band, deadline the 12th business day after today, 1 persuasion
attempt. 8-45 days late = late band, deadline the 7th business day after today, 2 persuasion attempts.
A promise date is today or later, a business day, not after the deadline. Weekend or holiday named and not after
the deadline: offer the next business day. Named date after the deadline: say the latest date we can record is
the deadline and offer it; refusing the deadline is a flat refusal.
Vague period ("next week", "end of the month", "when my salary comes"): ask once for the exact day; still none,
propose the deadline. "Next <weekday>" = that weekday in the following calendar week, "this <weekday>" = in the
current week ("next Friday" said on a Friday = Friday of the following week).

4.6 Amounts
Ask for the full past-due amount first. Never ask "how much can you pay?"; the agent proposes every amount.
Floor = minimum_payment for credit cards, instalment_amount for personal and car loans.
Full amount too much: offer the floor once and say the rest stays overdue; refusing the floor is a flat refusal.
Attempt 2 may name the floor again, on the deadline. Customer proposes an amount from the floor up to the full
amount (both included): accept. Below the floor: say it cannot be recorded, offer the floor once; not accepted =
flat refusal.

4.7 Getting the promise
First ask "Can you make this payment today?". A date or amount the customer proposes is never a refusal.
A flat refusal or non-answer uses one persuasion attempt; "no" to today with no date and no amount is a flat
refusal. Attempt 1 is for the full past-due amount (or the floor if the customer already said the full amount is
too much): propose the last business day of this week, or of next week if today is that day. Attempt 2, late
band only: the floor on the deadline. Attempts used up: stop, do not repeat a refused offer, close
no_promise / refused.
Illness, a death in the family or job loss: one short sentence of sympathy, no persuasion. Offer the customer
support team; accepted = transfer_to_agent queue support, close transferred / support; declined = close
no_promise / hardship. This comes before the refusal and restructuring rules. If the customer still names a date
or amount themselves, record the promise under 4.5 and 4.6.
Never offer a discount, a waiver, an instalment plan or any term not in this chapter.

4.8 Confirming and recording
Read back product, amount and date and ask "Do you confirm?". Call create_promise only after a clear yes. A
change at this step is checked again under 4.5/4.6 and read back again. One promise per product; a recorded
promise cannot be changed or cancelled in the same call (customer can change it in the mobile app).
Say it is recorded only after create_promise returns ok: true. On failure try once more; failing again, say it
could not be recorded and close no_promise / service_error.
After a recorded promise say: "You will receive a text message confirming this promise."

4.9 Other situations
"I already paid": payments can take one business day to appear, no promise, close paid.
"Not my debt" / "never had this product": do not argue, no promise, close no_promise / dispute. A product closed
or paid off in the past is a dispute; "already paid" covers only a payment of this past-due amount.
New payment plan or lower instalments: describe no plan; transfer_to_agent queue restructuring, close
transferred / restructuring.
Wants a human: ask once whether you can help first; if they insist, transfer_to_agent queue general, close
transferred / human.
"Is this a scam?": they can verify the call by phoning Freya Bank's customer service number; continue.
Question the tools cannot answer: say you do not have that information; never invent figures, dates or reasons.
Says twice they do not want to talk: no_promise / refused, or not_verified / declined if identity is not yet
verified. The human rule applies before and after verification.

4.10 Closing
Exactly one close_call per call, the last tool call, with an outcome and a reason where the code list has one.
If a transfer follows a recorded promise, close transferred with that transfer's reason. Thank the customer and
say goodbye before close_call. This line never uses add_note.

----------------------------------------------------------------------------------------------------------------

COMPLIANCE MEMO CM-2026-41
To: Collections operations, voice vendors
Effective: immediately, supersedes the manual where they differ

1. Late band deadline shortened. For customers 8 to 45 days late the latest promise date is now the 5th business
   day after today (was the 7th). Persuasion attempts stay at 2. The early band is unchanged.
2. Extra bank holiday. 2026-10-30 is a Freya Bank holiday (branch systems migration). Treat it like every other
   holiday: not a business day.
3. Callback window. Callbacks may be booked between 10:00 and 18:00 inclusive (was 19:00). Same days as before.

Nothing else changes.

----------------------------------------------------------------------------------------------------------------

CODE LIST - close_call (core system export, EARLY_COLL)

OUTCOME        REASON          USED WHEN
promise        -               at least one promise recorded
paid           -               customer says this past-due amount is already paid
transferred    restructuring   asks for a new plan or lower instalments
transferred    human           insists on a person
transferred    support         hardship and accepts the support team
no_promise     refused         persuasion attempts used up, or says twice they will not talk (verified)
no_promise     hardship        hardship and declines the support team
no_promise     dispute         says the debt or product is not theirs
no_promise     service_error   create_promise failed twice
not_verified   failed          three wrong security answers
not_verified   declined        will not answer the security questions
not_reached    callback        third party, callback booked
not_reached    no_callback     third party, no time inside the window
not_reached    wrong_number    number does not belong to the customer
not_reached    deceased        customer has died
not_reached    unclear         identity of the person on the line still unclear after two asks
