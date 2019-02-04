portalz
=======
![Human Character Components](https://g.gravizo.com/source/human_character?https%3A%2F%2Fraw.githubusercontent.com%2Fbrotherdetjr%2Fportalz%2Fmaster%2FREADME.md)
<details>
<summary></summary>
human_character
@startuml

actor Player

package "Per-Character Components" {
    [Replay Stopper] <<inactive>> as RS
    () " " as Dot1

    RS <.. [Perception Log] #888888
    RS <.. [Sensory System] #888888
    [Sensory System] --> Dot1 : Perception
    Dot1 --> [Perception Log]
    Dot1 --> [UI]
    Dot1 --> [Reactor]
    [UI] <--> Player
}

database World

World --> [Sensory System] : States
World <-- [Reactor] : Reaction
[UI] --> World : Reaction

skinparam component {
  backgroundColor<<inactive>> #f0f0f0
  borderColor<<inactive>> #888888
  fontColor<<inactive>> #888888
  stereotypeFontColor<<inactive>> #888888
}

hide stereotype

@enduml
human_character
</details>
