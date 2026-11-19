# The 3-minute demo

For showing Pramaan to someone who knows products, not code. Rehearse it twice on the live site, on a phone, before the real thing.

**Before you start (5 minutes, every time)**
1. Open https://pramaan-rose-chi.vercel.app on your phone and on a laptop a few minutes early. This wakes the server. If you see "Waking up the server", wait for it to clear.
2. Check the certificate you will scan: open its `/verify/<code>` page and make sure it says **Authentic**. If it says anything else, stop and fix that first.
3. Have the **edited copy** of the certificate file ready on your laptop (see "The edited copy" below).
4. Sign out of any account. Use a fresh, normal browser window.

**The story in one line:** "Anyone can claim they won an award. Pramaan is where the claim comes with proof, and anyone can check it in seconds."

## 0:00 to 0:30. The problem and the home page
- Open the home page. Say: "Anyone can write 'award-winning' on a profile. Here, every achievement shows how it was checked."
- Point at the three numbers under the heading (people verified, certificates, joined this month). They are real: demo people are never counted.

## 0:30 to 1:15. Find someone, in plain language
- Tap **Find people**. Type: *women scientists in Kerala* (or any sentence). Say: "I did not pick a filter. I asked a question."
- Open one profile. Show the line under each achievement: *Confirmed by a reviewer* or *Document verified*. Say: "A person, not an AI, signs off the doubtful ones."
- Show **Hindi works too**: type *सौर ऊर्जा वैज्ञानिक*.

## 1:15 to 2:00. Get listed by talking
- Tap **Get listed**. Tick the first box. Say: "Nothing is public until I agree, and nothing is looked up about me unless I tick the second box."
- Start the chat. Type one sentence: "I'm <name>, I teach physics in Pune and won the <award> in 2023." Show the profile building on the right.
- Say: "I did not fill in a form."

## 2:00 to 2:45. The certificate and the check
- Open an existing certificate. Say: "Each one has a QR code and is written into a public log."
- **Scan the QR with the phone camera.** It opens the check page: **Authentic**, five checks ticked.
- Open **Transparency**: "This list is public. If anyone, including us, changed an old entry, this button would fail." Press **Verify the whole chain**.

## 2:45 to 3:00. The edited copy (the moment that lands)
- Drop the **edited copy** into the file box on /verify. It fails the check.
- Close with: "A certificate you can check is worth more than one you have to trust."

## The edited copy
1. On the certificate's check page, press **JSON (offline check)**. This downloads the signed certificate as a `.json` file.
2. Open the file in any text editor, change one word (for example the person's name), and save it under a new name.
3. On **/verify**, drop the edited file into the box that says *Drop a certificate file (.json) to check it on this device*. It fails the check. Drop the original once first: it passes.
4. Practise this once. If an edited file ever shows as genuine, **stop and tell the developer**.

## If something goes wrong
| What you see | What to do |
|---|---|
| "Waking up the server" for more than a minute | Say "the free server is waking up", open /transparency in another tab, and try again. |
| "Cannot be confirmed right now" on a certificate | The server lost a signing key. Do not demo that certificate; use another one and tell the developer. |
| The email code does not arrive | The error on the page names the reason (for example network_blocked or sender_not_verified). For the demo, use a profile that is already signed in. |
| Search returns nothing | Try one of the example questions on the page. |

## What to say when asked
- **"Who decides?"** Rules and a person decide. The AI only helps read and suggest, and it never has the final say.
- **"What if the AI is wrong?"** Anything doubtful goes to a person, and every error goes to a person too. Nothing is approved because of an error.
- **"Can you fake a certificate?"** You can print one, but it fails the check. The check does not trust us: your own browser re-computes it.
- **"How many people are on it?"** Say the real number from the home page. Do not include the demo people.
