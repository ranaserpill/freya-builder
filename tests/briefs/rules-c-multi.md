From: Collections Policy Desk <policy@auroracu.example>
To: Voice vendor
Date: 6 October 2026
Subject: Addendum - members behind on more than one product, plus calendar change

Hello,

This addendum extends the arrears brief you already have to members who are behind on up to three products.
Everything in the arrears brief still applies unless this mail replaces it. Aurora Credit Union is fictional and
all data is synthetic.

CALENDAR CHANGE (applies to every call, one product or several)
- 2026-11-02 is no longer a holiday: branches open that day.
- 2026-11-03 is a holiday instead.

MULTI-PRODUCT RULES
A. get_account returns one to three products, each with its own past_due, days_late and minimum.
B. Name every overdue product, one sentence each, before asking for anything.
C. The stage, the latest date and the persuasion attempts are worked out per product from that product's
   days_late. Two products of the same member can have different latest dates.
D. First ask whether the member can pay everything today. If not, go through the products one at a time, in the
   order get_account returned them. Do not ask about today again for each product. Each product starts at
   attempt 1.
E. If the member gives one date for everything and it is after one product's latest date, record that product on
   its own latest date and say so in the read-back. The other products keep the member's date.
F. Read every commitment back together and ask for one confirmation ("Is that correct?"). Then call
   create_promise once per product.
G. For every product that ends without a commitment, call add_note with that product_id and one of the reasons in
   the code list below. This also applies when no product gets a commitment.
H. "Already paid" or "not mine" on one product does not end the call: note it and continue with the others.
I. A payment-plan request still transfers the call. Commitments recorded before it stay; agreed but unrecorded
   ones are not recorded. On any transfer add no notes at all.
J. If create_promise fails three times for one product, keep the commitments already recorded and note that
   product with system_error.

CLOSING WITH SEVERAL PRODUCTS
committed wins whenever at least one commitment was recorded (except rule I: escalated). With no commitment: if
every product is noted settled, close settled; otherwise close declined with the reason of the first product, in
get_account order, whose note is not settled.

CODE LIST - add_note.reason
refusal         member refused after the persuasion attempts
vulnerability   illness, bereavement, job loss or other vulnerability, welfare team declined
contested       member says the product is not theirs
settled         member says this product is already paid
system_error    create_promise failed three times

Regards,
Collections Policy Desk
