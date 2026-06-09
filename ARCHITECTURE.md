# ProsodyPrompt Architecture & Data Flow

## System Overview

```mermaid
graph LR
    A["🎵 Original Audio<br/>WAV File"] 
    B["🔤 Transcription<br/>WhisperX"]
    C["📍 Alignment<br/>MFA/WhisperX"]
    D["🎵 Pitch Extraction<br/>pYIN/CREPE"]
    E["📋 Prosody Annotation<br/>SpeechPrint"]
    
    F["📁 TextGrid<br/>with Prosody Tier"]
    
    G["✏️ Prosody Resynthesis<br/>Edit Symbols"]
    H["📊 F0 Compiler<br/>Symbols → F0 Targets"]
    I["🎙️ Voice Synthesis<br/>Coqui TTS"]
    J["🎵 Resynthesized Audio<br/>with Modified Prosody"]
    
    K["🌐 Speech DAW<br/>Interactive Timeline Editor"]
    
    A --> B --> C --> D --> E --> F
    F --> G
    F --> K
    
    G --> H --> I --> J
    K --> H --> I --> J
    
    style A fill:#e1f5ff
    style F fill:#fff9c4
    style J fill:#c8e6c9
    style K fill:#f3e5f5
```

## Detailed Data Flow: Resynthesis Path

```mermaid
sequenceDiagram
    participant User
    participant CLI as resynthesis_cli.py
    participant Editor as ProsodyEditor
    participant Compiler as F0Compiler
    participant TTS as CoquiSynthesizer
    participant Output as Output Files
    
    User->>CLI: Load TextGrid + audio
    CLI->>Editor: Load TextGrid
    Editor->>Editor: Parse syllables
    
    User->>CLI: Edit symbol
    CLI->>Editor: modify_symbol()
    Editor->>Editor: Update internal state
    
    User->>CLI: Compile & synthesize
    CLI->>Compiler: compile_syllable()
    Compiler->>Compiler: Parse symbol
    Compiler->>Compiler: Compute F0 targets
    Compiler-->>CLI: F0Target list
    
    CLI->>TTS: Clone voice from audio
    TTS->>TTS: Compute speaker embedding
    TTS-->>CLI: Speaker ready
    
    CLI->>TTS: synthesize(text, f0_targets)
    TTS->>TTS: Generate speech with F0 control
    TTS-->>CLI: Audio waveform
    
    CLI->>Output: Save TextGrid
    CLI->>Output: Save WAV
    CLI-->>User: Done
```

## Speech DAW: Web Architecture

```mermaid
graph TB
    subgraph Browser ["🌐 Browser (Client)"]
        UI["HTML/CSS/JS<br/>Timeline Editor"]
        State["Local State<br/>Syllables + Edits"]
    end
    
    subgraph Server ["🖥️ FastAPI Server"]
        API["REST API<br/>8 Endpoints"]
        Editor2["ProsodyEditor<br/>In-Memory"]
        Compiler2["F0Compiler<br/>On Demand"]
        TTS2["CoquiSynthesizer<br/>On Demand"]
    end
    
    subgraph Data ["💾 Data"]
        TG["TextGrid Files"]
        Audio["Audio Files"]
    end
    
    UI -->|Click syllable| State
    State -->|POST /api/syllable/edit| API
    API -->|Update| Editor2
    API -->|Return JSON| State
    State -->|Render| UI
    
    API -->|Read| TG
    API -->|Read| Audio
    Editor2 -.->|Use| TG
    Compiler2 -.->|Use| Editor2
    TTS2 -.->|Use| Audio
    
    UI -->|POST /api/synthesize| API
    API -->|Compile| Compiler2
    API -->|Synthesize| TTS2
    API -->|Return F0 summary| State
    
    style Browser fill:#e3f2fd
    style Server fill:#fff3e0
    style Data fill:#f3e5f5
```

## Module Dependencies

```mermaid
graph LR
    subgraph Core["Core Modules"]
        FC["f0_compiler.py<br/>(Symbols → F0)"]
        TIO["textgrid_io.py<br/>(TextGrid I/O)"]
        CI["coqui_interface.py<br/>(TTS + Voice Clone)"]
        PE["prosody_editor.py<br/>(Interactive Edit)"]
        Utils["utils.py<br/>(Helpers)"]
    end
    
    subgraph Apps["Applications"]
        CLI["resynthesis_cli.py<br/>(CLI Tool)"]
        Server["speech_daw_server.py<br/>(Web Server)"]
        Web["speech_daw_ui/<br/>(Web Frontend)"]
    end
    
    subgraph External["External"]
        Librosa["librosa<br/>(F0 extraction)"]
        Coqui["TTS/Coqui<br/>(Synthesis)"]
        FastAPI["FastAPI<br/>(Web framework)"]
    end
    
    FC --> Utils
    TIO --> Utils
    CI --> Librosa
    CI --> Coqui
    PE --> FC
    PE --> TIO
    
    CLI --> PE
    CLI --> CI
    
    Server --> PE
    Server --> Compiler["F0Compiler"]
    Server --> CI
    Server --> FastAPI
    Web --> Server
    
    Compiler --> FC
    
    style Core fill:#e8f5e9
    style Apps fill:#f3e5f5
    style External fill:#fce4ec
```

## Symbol Compilation Pipeline

```mermaid
graph LR
    Sym["Prosody Symbol<br/>e.g. *‾//"]
    
    Parse["Parse Components"]
    Accent["Has Accent?<br/>* = yes"]
    Height["Height Level<br/>‾ = high, _ = low"]
    Dir["Direction<br/>/ = rising, \ = falling"]
    Voiced["Voiced?<br/>? = no"]
    
    OnsetF0["Compute Onset F0<br/>= ref ± height_offset<br/>+ accent_boost"]
    OffsetF0["Compute Offset F0<br/>= ref × 2^(direction_st/12)"]
    
    Trajectory["Generate Trajectory<br/>Rising: slow→fast<br/>Falling: fast→slow<br/>Level: constant"]
    
    Targets["F0Target List<br/>with timing"]
    
    Sym --> Parse
    Parse --> Accent
    Parse --> Height
    Parse --> Dir
    Parse --> Voiced
    
    Accent --> OnsetF0
    Height --> OnsetF0
    Dir --> OffsetF0
    
    OnsetF0 --> Trajectory
    OffsetF0 --> Trajectory
    Voiced --> Trajectory
    
    Trajectory --> Targets
    
    style Sym fill:#fff9c4
    style Targets fill:#c8e6c9
    style Parse fill:#e0e0e0
```

## Coqui TTS Synthesis Flow

```mermaid
graph LR
    Voice["Reference Audio<br/>15-30 seconds"]
    Text["Text to Synthesize"]
    F0["F0 Targets<br/>Optional"]
    
    Extract["Extract Speaker<br/>Embedding"]
    Normalize["Normalize Audio<br/>16 kHz"]
    
    TTS["Glow-TTS<br/>Text → mel-spectrogram"]
    Vocoder["HiFi-GAN Vocoder<br/>mel → waveform"]
    
    PitchShift["Apply F0 Control<br/>PSOLA-style<br/>Optional"]
    
    Output["Output Audio<br/>WAV"]
    
    Voice --> Extract
    Voice --> Normalize
    Extract --> TTS
    Normalize -.->|For matching| TTS
    
    Text --> TTS
    TTS --> Vocoder
    F0 -.->|Optional| PitchShift
    Vocoder --> PitchShift
    PitchShift --> Output
    
    style Voice fill:#ffccbc
    style Text fill:#c8e6c9
    style F0 fill:#fff9c4
    style Output fill:#b3e5fc
```

## REST API Endpoints

```mermaid
graph TB
    subgraph Lifecycle["Project Lifecycle"]
        P1["POST /api/project/new<br/>→ Load TextGrid + Audio"]
        P2["GET /api/project<br/>→ Get current project info"]
    end
    
    subgraph Editing["Syllable Editing"]
        E1["GET /api/syllables<br/>→ Get all syllables"]
        E2["POST /api/syllable/{id}/edit<br/>→ Modify one syllable"]
        E3["POST /api/syllable/{id}/reset<br/>→ Revert to original"]
    end
    
    subgraph Output["Synthesis & Export"]
        O1["POST /api/synthesize<br/>→ Compile F0 targets"]
        O2["POST /api/export<br/>→ Save modified TextGrid"]
        O3["GET /api/export/download<br/>→ Download TextGrid"]
    end
    
    subgraph Monitor["Monitoring"]
        M1["GET /api/health<br/>→ Server status"]
    end
    
    P1 --> P2
    P2 --> E1
    E1 --> E2
    E2 --> E1
    E2 --> E3
    E1 --> O1
    E1 --> O2
    O2 --> O3
    P1 -.-> M1
    
    style Lifecycle fill:#e3f2fd
    style Editing fill:#f3e5f5
    style Output fill:#c8e6c9
    style Monitor fill:#fff9c4
```

## File Organization

```mermaid
graph LR
    Root["ProsodyPrompt/"]
    
    Linux["linux/"]
    Run["run.py<br/>(Main CLI)"]
    Build["build_*.py<br/>(Build scripts)"]
    
    Resyn["prosody_resynthesis/"]
    RFiles["__init__.py<br/>f0_compiler.py<br/>textgrid_io.py<br/>coqui_interface.py<br/>prosody_editor.py<br/>utils.py"]
    
    ResynCLI["resynthesis_cli.py<br/>(Interactive editing)"]
    DAWServer["speech_daw_server.py<br/>(Web API)"]
    DAWFiles["speech_daw_ui/<br/>index.html<br/>style.css<br/>app.js"]
    
    Docs["📖 RESYNTHESIS_README.md<br/>📖 SPEECH_DAW_README.md<br/>📖 ARCHITECTURE.md"]
    
    Root --> Linux
    Root --> Docs
    
    Linux --> Run
    Linux --> Build
    Linux --> Resyn
    Linux --> ResynCLI
    Linux --> DAWServer
    Linux --> DAWFiles
    
    Resyn --> RFiles
    
    style Resyn fill:#e8f5e9
    style ResynCLI fill:#f3e5f5
    style DAWServer fill:#fff3e0
    style DAWFiles fill:#e3f2fd
```

## Status Legend

- ✅ **Implemented & Tested**
- ⚠️ **Implemented, Not Fully Tested**
- 🔄 **Partially Implemented**
- 📋 **Design Only**

### Current Status

| Component | Status |
|-----------|--------|
| F0 Compiler | ✅ Works |
| TextGrid I/O | ✅ Works |
| ProsodyEditor | ⚠️ Works with prosody tier |
| Coqui Interface | ⚠️ Wrapper written, TTS not installed |
| Resynthesis CLI | ⚠️ Code complete, end-to-end untested |
| Speech DAW Server | ⚠️ API endpoints work, state management partial |
| Speech DAW UI | ⚠️ HTML/JS complete, not tested in browser |

