Temporta
========

## General Idea
The goal is to make a multiplayer videogame with time-travelling.

Even [a one-player game](https://en.wikipedia.org/wiki/Braid_(video_game)) with time-travelling is somewhat non-trivial. However, in the one-player game, the general approach seems obvious: you write log of the game and then "rewind" to a given logged state when needed. 

This approach has obvious drawbacks when applied to a multiplayer game: you have to throw back to the past all the players at once. This might be useful under some circumstances, but it does not look like a universal approach.

The general idea is to write a log as for the one-player game, but "rewind" the state only for a single player, creating an alternative branch of the game world.

On the one hand the new branch should behave similarly to the original one, but on the other hand it should react to your actions. This can be easily achieved if we have a fully-deterministic game world: we just need to restore certain game state and let it evolve according to the prescribed deterministic laws.

However, in a multiplayer game, we have **in**deterministic players' behaviour. We can record the actions of each player character and then replay them in the alternative branch until the character needs to react to something new introduced by your actions. Let's call this *handover of control*, because the character cannot be controlled by the recorded action log anymore, and needs to be controlled somehow else.

The reaction to the new impacts can vary. It can be trivial: e.g. "replaying" character may freeze or even die. It can be complex with help of AI. Another option is to allow the player who owns this character in the original branch to control it in the alternative one.

Every approach has its own drawbacks. Freezing or dying may seriously damage the gameplay because this kind of reaction is pretty unrealistic. The AI can bring more realism, but it is much more difficult to develop and still does not guarantee an adequate reaction. Manual control can overflow the player's mind: they will need to control multiple characters at once.

We could put the branch on pause until the player responded to a suggestion to control yet another character.  However, this impacts the gameplay heavily. The best solution seems to be a combination of the above approaches. It will be discussed further.

Another question is what is that "something new" the character has to react to. Every player character should have a record of their perception &mdash; everything the player was able to observe on their game screen. When the actual perception diverges from the recorded one, this means the character experiences "something new", and the handover of control is needed.

## State of the Project
At the moment, the project is in its earliest state. Every related document should be considered as draft.

However, the initial idea was described in 2013 ([Russian](https://docs.google.com/document/d/1axiG1gClkzi3uJmkCTpP5wvLg5ag31wS_JMv_VkOXlU/edit?usp=sharing)).

## Project Name
It's still TBD. [Temporta](https://translate.google.com/#view=home&op=translate&sl=pt&tl=en&text=temporta) is translated as "it matters" from Portuguese by Google. This sounds neutral and intriguing. Also, it is a portmanteau of "temporal" and "portal": the portals are supposed to be the main mean of time-travelling in the game.

## Algorithms and Entities
- `World` &mdash; contains `State`s and provides some of them to a `Sensory System` and receives `Reaction`s. Deterministically changes the `State`s according to received `Reaction`.
- `Sensory System` &mdash; receives `State`s and converts them to a `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function). `State`s can be both internal (i.e. belonging to a character) and external (i.e. belonging to a character's observed neighborhood).
- `Reactor` &mdash; produces a `Reaction` on given `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function) too.

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter.uml)

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter-replay.uml)

## Sample Mission
1. You travel between three lined up stations &mdash; A, B and C. Station B stands between A and C. It takes one hour to get from A to B or vice versa. It takes two hours to get from B to C or vice versa. Obviously, it will take 1 + 2 = 3 hours to get from A to C.
2. You arrive at B at midnight.
3. A small item X will come to station A at 3 am and expire in a bit more than one hour after that. You can pick the items, or you can drop them where you are at the moment. You can do it as many times as you wish. The items are small, thus you can take and carry as many of them as you wish.
4. Another item Y will come to C at 6 am and expire in a bit more than one hour as well.
5. Your goal is to take the items to station B so that you had them both there, and none of the items were expired at the moment. This is needed because the items are the short-living halves of some mechanism you need to activate at B.
6. Obviously, you need A TIME MACHINE!
7. You have one, and it works as follows. In any place (not only at the stations but between them too) you set the portals: one inbound and one outbound. You may set them the other way round. Also, you may set them next to each other if you want, or far away.
8. Then you need to activate your time machine. You can do it at any time, even when you are far away from the portals. However, you cannot move the portals after you activated them. Please note, that you can activate the time machine only AFTER you set the portals.
9. Then you can enter the inbound portal whenever you like. You will appear on the "outbound" side right at the moment you activated your time machine!
10. You won't face any kind of [grandfather paradox](https://bit.ly/2toRlz6), because you travel into an "alternative branch" of your past. Also don't be afraid of meeting yourself from the past there.
11. Passing through the portals, their settlement and activation take almost no time.
12. You can time-travel with the items you take, of course.
13. However, they don't get younger passing through the portals. Nor you do, unfortunately. E.g. you hold an item for half an hour, then jump into the portal to 100 years ago, and hold the item for 30 minutes more. It will get older for 0.5 + 0.5 = 1 hour. No tricks here.
14. In this particular quest, you've got a one-and-only time machine (consisting of two portals). Moreover, you cannot DEactivate it after you turned it on.

<details>
<summary>Solution</summary>

- 0:00 - You arrive at B. Set up the outbound portal[¹]. Start moving towards C.
- 1:00 - Halfway to C you stop and set up the inbound portal. Then Start moving towards A.
- 3:00 - You arrive at A. Pick item X, start moving towards B.
- 4:00 - You arrive at B. Drop item (it still has a little bit of time before it expires). Activate the time machine. Start moving towards C.
- 6:00 - You arrive at C. Pick item Y, start moving towards the inbound portal.
- 7:00 - You reach the portal. Jump into it.
- 4:00 - You walk out of the portal at B. Both items are with you and have not expired yet.

##### ¹ You can set the outbound portal later on your way to A, or even later when you bring item X to B.
[¹]:#-you-can-set-the-outbound-portal-later-on-your-way-to-a-or-even-later-when-you-bring-the-item-x-to-b
</details>

### Additional Details Unrelated to This Mission
- You can go back to the future just entering an outbound portal. You will walk out of the inbound one.
- However, the branch you are returning to was not "frozen", while you were traveling back in time, and you will return to its "bleeding edge" &mdash; NOT to the moment you left it. E.g. at midnight you jump back in time for 100 years. You spend there half an hour and then jump back to the future. You will walk out of the portal at 0:30.
- Any other person from the past may enter your outbound portal, this allows them to travel to the future.
