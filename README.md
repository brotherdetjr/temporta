portalz
=======
- `World` &mdash; contains `State`s and provides some of them to a `Sensory System`. Receives `Reaction`s. Deterministically changes the `State`s according to received `Reaction`.
- `Sensory System` &mdash; receives `State`s and converts them to a `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function). `State`s can be both internal (i.e. belonging to a character) and external (i.e. belonging to a character's neighborhood).
- `Reactor` &mdash; produces a `Reaction` on given `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function) too.

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter.uml)

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter-replay.uml)

## Sample Mission
1. You travel between three lined up stations - A, B and C. It takes one hour to get from A to B or vice versa. It takes two hours to get from B to C or vice versa. Obviously, it will take 1 + 2 = 3 hours to get from A to C.
2. You arrive at B at midnight.
3. A small item X will come to station A at 3 am and expire in a bit more than one hour after that. You can pick the items, or you can drop them where you are at the moment. You can do it as many times as you wish.
4. Another item Y will come to C at 6 am and expire in a bit more than one hour as well.
5. Your goal is to take the items to station B so that you had them both there, and none of the items were expired at the moment. This is needed because the items are the short-living halves of some mechanism you need to activate at B.
6. Obviously, you need A TIME MACHINE!
7. You have one, and it works as follows. In any place (not only at the stations but between them too) you set the portals: one inbound and one outbound. You may set them the other way round. Also, you may set them next to each other if you want, or far away.
8. Then you need to activate your time machine. You can do it at any time, even when you are far away from the portals. However, you cannot move the portals after you activated them. Please note, that you can activate the time machine only AFTER you set the portals.
9. Then you can enter the inbound portal whenever you like. You will appear on the "outbound" side right at the moment you activated your time machine!
10. You won't face any [grandfather paradox](https://bit.ly/2toRlz6), because you travel into an "alternative branch" of your past. Also don't be afraid of meeting yourself from the past there.
11. Passing through the portals, their settlement and activation take almost no time.
12. You can time-travel with the items you take, of course.
13. However, the items don't get younger passing through the portals. Nor you do, unfortunately. E.g. you hold an item for half an hour, then jump into the portal to 100 years ago, and hold the item for 30 minutes more. The item will get older for 0.5 + 0.5 = 1 hour. No tricks here.
14. In this particular quest, you've got one-and-only time machine (consisting of two portals). Moreover, you cannot DEactivate it after you turned it on.

<details>
<summary>Solution</summary>

- 0:00 - You arrive at B. Set up the outbound portal. Start moving towards C.
- 1:00 - Halfway to C you stop and set up the inbound portal. Then Start moving towards A.
- 3:00 - You arrive at A. Pick the item X, start moving towards B.
- 4:00 - You arrive at B. Drop the item (it still has a little bit of time before it expires). Activate the time machine. Start moving towards C.
- 6:00 - You arrive at C. Pick the item Y, start moving towards the inbound portal.
- 7:00 - You reach the portal. Jump into it.
- 4:00 - You walk out of the portal at B. Both items are with you and have not expired yet.

</details>
