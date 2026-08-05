# Tesla Fleet API CLI

A tool that lets you check on and control a Tesla car from a computer,
without opening the Tesla mobile app. It talks directly to Tesla's own
official API — the same system the Tesla app itself uses — so anything you
could tap a button for in the app, this can do from a script instead.

## What it actually does

At a high level, the project does two things:

**It checks on your car.** It can ask Tesla's servers whether the car is
awake, where it stands on battery charge, what the climate settings are,
whether the doors are locked, and dozens of other details — the same
information the Tesla app shows on its home screen.

**It controls your car.** Beyond just reading status, it can lock or unlock
the doors, start or stop climate control, open the charge port, start or
stop charging, set a charge limit, turn on Sentry Mode, vent the windows or
sunroof, flash the lights, honk the horn, and more — around 40 different
actions in total, covering nearly everything the official app can trigger
remotely.

Because it goes through Tesla's own systems rather than reverse-engineering
anything, it works the same way an authorized third-party app would: you
sign in with your real Tesla account, you approve access the same way you'd
approve any app, and Tesla treats every request the same as it would coming
from an official partner.

## Why this exists

The Tesla app is great for a person tapping buttons, but it has no way to
be automated. There's no way to tell it "lock the car every night at 11pm,"
or "text me if charging stops early," or "start the climate control
whenever my calendar says I'm about to leave work." Anyone who wants their
Tesla to participate in that kind of automation has to talk to Tesla's
underlying API themselves — and that API is intentionally locked down, both
for security and because Tesla wants to know which apps are accessing a
car and why.

This project is that missing piece: the plumbing needed to safely and
correctly talk to Tesla's official API, already built, so it can be reused
as a building block for other ideas (automations, dashboards, notifications,
integrations with other smart-home tools, etc.) instead of everyone having
to build that plumbing from scratch.

## How the "talking to Tesla" part works, in plain terms

Getting a program to control a real car isn't as simple as sending it a
web request — Tesla has two layers of protection in place, and this project
respects both of them:

1. **Signing in.** The first step is a normal login: you're sent to Tesla's
   real login page, you sign in with your Tesla account exactly as you
   would in the app, and you approve the specific permissions being
   requested (e.g. "see vehicle data" or "send commands"). Tesla then hands
   back a pair of digital keys that prove who you are for future requests,
   so you don't have to log in again every time.

2. **Proving a command is really from you.** Simply checking on a car (like
   asking "what's the battery level?") is low-risk, so that part talks to
   Tesla directly. But *commands* — anything that actually changes something
   about the car, like unlocking a door — go through an extra layer of
   protection that Tesla requires for newer vehicles: every command has to
   be digitally signed with a private key that only you hold, using a small
   helper program that Tesla itself publishes. That signed command is then
   what actually reaches the car. This is the same protection Tesla's own
   app relies on; it exists so that a stolen login alone can never be
   enough to, say, remotely unlock someone's car.

Once both of those are set up, the everyday experience is simple: run a
command, get back exactly what the car did.

## What makes this different from a typical "Tesla dashboard"

Most hobby projects around Tesla's API are visual dashboards meant to be
looked at. This one is deliberately the opposite — it has no screen at all.
It's built to be *used by other programs and scripts*, which makes it a
building block rather than a destination: something you could wire into a
home-automation system, a scheduled task, a notification bot, or a future
dashboard, rather than something you sit and stare at.

It also doesn't cut corners on the security requirement described above.
A lot of simpler example projects skip the command-signing step entirely
and only work on older vehicles as a result; this one implements it
properly so it keeps working on current Tesla models.

## Vehicles supported

Everything works per-vehicle, so an account with multiple Teslas is fully
supported — you can list every vehicle on the account and direct any check
or command at a specific one.

## What it's built with

It's written in Python, using Tesla's own official API and Tesla's own
official command-signing helper program — no unofficial or reverse-engineered
endpoints. There's no database, no server, and no visual interface; it runs
locally as a lightweight command-line tool, and everything it knows about
your car comes fresh from Tesla each time rather than being stored.

## Things worth knowing

- A car that's asleep takes a moment to respond to the first command after
  a while of inactivity — same as it would in the app.
- Login credentials and access keys are kept only on your own machine, never
  sent anywhere except to Tesla itself.
- Tesla occasionally adjusts details of its API, so this is treated as a
  living project that may need small updates over time to stay in sync.

---

*For the technical setup steps (installing dependencies, configuring API
credentials, running the command-signing helper), see the code comments and
`.env.example` in this repository.*
