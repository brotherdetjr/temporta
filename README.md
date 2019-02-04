portalz
=======
- `World` &mdash; contains `State`s and provides some of them to a `Sensory System`. Receives `Reaction`s. Deterministicallly changes the `State`s according to received `Reaction`.
- `Sensory System` &mdash; receives `State`s and converts them to a `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function). `State`s can be both internal (i.e. belonging to a character) and external (i.e. belonging to a character's neigborhood).
- `Reactor` &mdash; produces a `Reaction` on given `Perception`. Works as a [pure function](https://en.wikipedia.org/wiki/Pure_function) too.

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter.uml)

![Human Character Components](https://g.gravizo.com/source?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2Fcharacter-replay.uml)
