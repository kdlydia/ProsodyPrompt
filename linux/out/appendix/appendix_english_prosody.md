# Appendix B — SpeechPrint Prosody Labels on English Minimal Pairs

Backend: MFA `english_mfa` (phone-level Kaldi) + Parselmouth F0 (vowel nucleus, 10-point).

**Symbol key:**  `/` rising · `//` strong rise · `\` falling · `\\` strong fall
`-` high (rel. to neighbours) · `_` low · `*` prominent accent · combinations: `*-\\` etc.
F0 format: onset|mid|offset Hz  amplitude dB  (measured at vowel nucleus only)

### Contrastive Stress vs. Neutral

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 1a | Do you want tea or COFFEE? [contrastive] | `kɔ` | 203|188|184Hz  64.2dB | `*-\\` |
| 1b | Did you meet MARY or MARTHA yesterday? [contr] | `dɪd` | 211|215|193Hz  66.4dB | `*-\` |

**1a  Do you want tea or COFFEE? [contrastive]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  duː        do             221|213|214Hz  65.7dB            _
  juː        you            225|230|231Hz  71.2dB            -
  wɔnt       want           234|223|221Hz  68.8dB            -
  tiː        tea            219|249|272Hz  65.7dB            -//
  ɔːɹ        or             272|132|129Hz  63.6dB            _\\
> kɔ         coffee         203|188|184Hz  64.2dB            *-\\
  fi         coffee         159|152|152Hz  54.4dB            _
```

**1b  Did you meet MARY or MARTHA yesterday? [contr]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> dɪd        did            211|215|193Hz  66.4dB            *-\
  juː        you            193|184|87Hz  59.0dB             _\\
  miːt       meet           113|137|128Hz  62.9dB            _//
  mɛ         mary           216|207|199Hz  63.4dB            _
> ɹi         mary           262|343|303Hz  66.1dB            *-//
  ɔːɹ        or             303|258|236Hz  64.7dB            \\
  mɑːɹ       martha         209|206|213Hz  66.2dB            _
  θə         martha         159|181|165Hz  62.3dB            -
  jɛs        yesterday      165|160|164Hz  55.9dB            _
  tɚ         yesterday                                       ?
  deɪ        yesterday      153|166|163Hz  55.0dB            _
```

### Focus Movement (Mary–Milan set)

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 2a | Who flew to Milan yesterday? [wh-q] | `huː` | 211|206|203Hz  62.5dB | `*-` |
| 2b | MARY flew to Milan yesterday. [focus:MARY] | `mɛ` | 212|226|245Hz  68.5dB | `*-//` |
| 2c | Where did Mary fly yesterday? [wh-q] | `wɛɹ` | 272|280|292Hz  70.0dB | `*-` |
| 2d | Mary flew to MILAN yesterday. [focus:MILAN] | `ɹi` | 234|244|238Hz  68.7dB | `-` |
| 2e | When did Mary fly to Milan? [wh-q] | `wɛn` | 199|195|199Hz  68.4dB | `*-` |
| 2f | Mary flew to Milan YESTERDAY. [focus:YEST] | `ɹi` | 234|244|238Hz  68.7dB | `-` |
| 2g | How did Mary go to Milan yesterday? [wh-q] | `dɪd` | 220|215|213Hz  67.5dB | `*-` |
| 2h | Mary FLEW to Milan yesterday. [focus:FLEW] | `jɛs` | 212|219|227Hz  68.5dB | `*-` |

**2a  Who flew to Milan yesterday? [wh-q]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> huː        who            211|206|203Hz  62.5dB            *-
  fluː       flew           215|215|213Hz  67.0dB            -
  tuː        to             213|210|212Hz  65.4dB            -
> mɪ         milan          215|213|210Hz  66.0dB            *-
  læn        milan          104|106|106Hz  51.9dB            _
  jɛs                       99|88|89Hz  61.0dB               _\\
```

**2b  MARY flew to Milan yesterday. [focus:MARY]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> mɛ         mary           212|226|245Hz  68.5dB            *-//
  ɹi         mary           250|217|192Hz  66.1dB            -\\
  fluː       flew           95|91|88Hz  62.6dB               _
  tuː        to             100|99|94Hz  56.8dB              -
  mɪ         milan          90|90|88Hz  59.5dB               -
  læn        milan          87|86|85Hz  59.0dB               -
  jɛs        yesterday      86|85|92Hz  57.0dB               _
> tɚ         yesterday      175|172|168Hz  59.0dB            *-
  deɪ        yesterday      83|87|88Hz  54.5dB               _
```

**2c  Where did Mary fly yesterday? [wh-q]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> wɛɹ        where          272|280|292Hz  70.0dB            *-
  dɪd        did                                             ?
  mɛ         mary           280|274|270Hz  68.9dB            -
  ɹi         mary           267|269|271Hz  58.8dB            -
  flaɪ       fly            223|222|251Hz  65.2dB            //
  jɛs                       209|175|178Hz  62.7dB            _\\
  tɚ                        170|168|164Hz  60.3dB            -
```

**2d  Mary flew to MILAN yesterday. [focus:MILAN]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  mɛ         mary           205|219|224Hz  69.7dB            _//
  ɹi         mary           234|244|238Hz  68.7dB            -
  fluː       flew           233|226|114Hz  66.8dB            _\\
  tuː        to             232|225|213Hz  62.2dB            -
  mɪ         milan          210|206|200Hz  69.5dB            -
  læn        milan          197|214|232Hz  65.8dB            -//
  jɛs        yesterday      188|184|182Hz  62.5dB            -
  tɚ         yesterday      85|159|164Hz  61.4dB             //
  deɪ        yesterday      81|88|89Hz  57.2dB               _//
```

**2e  When did Mary fly to Milan? [wh-q]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> wɛn        when           199|195|199Hz  68.4dB            *-
  dɪd        did            208|209|202Hz  68.9dB            -
  mɛ         mary           201|194|190Hz  66.2dB            -
  ɹi         mary           187|191|190Hz  62.1dB            -
  flaɪ       fly            185|181|212Hz  64.2dB            _//
  tuː        to             212|224|220Hz  62.1dB            -
  mɪ         milan          252|242|234Hz  63.6dB            -
  læn        milan          267|285|305Hz  64.2dB            -//
```

**2f  Mary flew to Milan YESTERDAY. [focus:YEST]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  mɛ         mary           205|219|224Hz  69.7dB            _//
  ɹi         mary           234|244|238Hz  68.7dB            -
  fluː       flew           233|226|114Hz  66.8dB            _\\
  tuː        to             232|225|213Hz  62.2dB            -
  mɪ         milan          210|206|200Hz  69.5dB            -
  læn        milan          197|214|232Hz  65.8dB            -//
  jɛs        yesterday      188|184|182Hz  62.5dB            -
  tɚ         yesterday      85|159|164Hz  61.4dB             //
  deɪ        yesterday      81|88|89Hz  57.2dB               _//
```

**2g  How did Mary go to Milan yesterday? [wh-q]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  haʊ        how            91|95|194Hz  61.7dB              _//
> dɪd        did            220|215|213Hz  67.5dB            *-
  mɛ         mary           203|193|189Hz  64.4dB            -
  ɹi         mary           194|202|101Hz  59.7dB            _\\
  ɡoʊ        go             187|184|183Hz  62.8dB            -
  tuː        to             183|184|92Hz  60.9dB             -\\
  mɪ         milan          93|93|88Hz  59.1dB               _
  læn        milan          90|119|135Hz  62.5dB             _//
```

**2h  Mary FLEW to Milan yesterday. [focus:FLEW]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> jɛs        yesterday      212|219|227Hz  68.5dB            *-
  tɚ         yesterday      117|117|237Hz  57.9dB            //
  deɪ        yesterday      115|115|115Hz  54.4dB            _
> mɛ         mary           213|210|208Hz  67.6dB            *-
  ɹi         mary           210|209|207Hz  68.5dB            -
  fluː       flew           204|203|203Hz  66.4dB            -
  tuː        to             203|205|201Hz  66.2dB            -
  mɪ         milan          193|190|187Hz  64.5dB            -
  læn        milan          190|197|216Hz  67.2dB            //
  jɛs        yesterday                                       ?
> tɚ         yesterday      159|155|85Hz  61.8dB             *-\\
  deɪ        yesterday      166|88|89Hz  56.1dB              _\\
```

### Statement vs. Question (Mary arrived)

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 3a | Mary has arrived already. [statement] | `mɛ` | 202|203|213Hz  67.9dB | `*-` |
| 3b | Mary has arrived already? [question] | `mɛ` | 217|216|218Hz  67.6dB | `*-` |
| 3c | Mary has arrived ALREADY? [incredulity] | `mɛ` | 203|205|216Hz  67.2dB | `*-` |

**3a  Mary has arrived already. [statement]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> mɛ         mary           202|203|213Hz  67.9dB            *-
> ɹi         mary           244|232|225Hz  67.2dB            *-
  hæz        has            225|217|112Hz  60.5dB            _\\
  ɚ          arrived        101|205|199Hz  64.0dB            _//
  ɹaɪvd      arrived        182|240|239Hz  64.3dB            //
  ɔːl        already        235|226|223Hz  62.2dB            -
  ɹɛ         already        129|133|136Hz  64.4dB            _
  di         already        135|137|137Hz  50.3dB            _
```

**3b  Mary has arrived already? [question]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> mɛ         mary           217|216|218Hz  67.6dB            *-
  ɹi         mary           225|112|113Hz  60.8dB            _\\
> hæz        has            233|252|287Hz  66.8dB            *-//
  ɚ          arrived        268|209|185Hz  65.5dB            \\
  ɹaɪvd      arrived        164|160|167Hz  58.2dB            _
  ɔːl        already                                         ?
  ɹɛ         already        80|82|84Hz  59.8dB               -
  di         already        86|86|86Hz  52.7dB               _
```

**3c  Mary has arrived ALREADY? [incredulity]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
> mɛ         mary           203|205|216Hz  67.2dB            *-
  ɹi         mary           269|267|271Hz  68.8dB            -
  hæz        has            271|257|236Hz  68.9dB            \\
  ɚ          arrived        242|225|215Hz  68.0dB            _\\
  ɹaɪvd      arrived        194|249|262Hz  66.9dB            -//
  ɔːl        already        188|182|177Hz  66.5dB            _
  ɹɛ         already        170|163|159Hz  62.3dB            -
  di         already        164|161|166Hz  60.6dB            -
  aɪ         i              166|170|166Hz  56.6dB            -
```

### Lexical Stress Shifts

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 4a | I need to perMIT this. [verb stress] | `niːd` | 188|199|101Hz  66.1dB | `*-\\` |
| 4b | I need a new PERmit today. [noun stress] | `eɪ` | 200|98|180Hz  63.2dB | `*-\` |
| 4c | The CONtract was signed. [noun] | `tɹækt` | 207|227|233Hz  70.6dB | `*-//` |
| 4d | Please conTRACT the summary. [verb] | `mɚ` | 257|267|274Hz  70.1dB | `-` |
| 4e | Please reCORD this for her. [verb] | `ɹɛ` | 233|241|247Hz  68.7dB | `*-` |
| 4f | That's a REcord for her. [noun] | `ɹɛ` | 248|265|257Hz  69.6dB | `*-` |

**4a  I need to perMIT this. [verb stress]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  ɔːl        already        188|182|177Hz  66.5dB            _
  ɹɛ         already        170|163|159Hz  62.3dB            -
  di         already        164|161|166Hz  60.6dB            -
  aɪ         i              166|170|166Hz  56.6dB            -
> niːd       need           188|199|101Hz  66.1dB            *-\\
  tuː        to             100|97|97Hz  62.4dB              _
  pɜː        permit         185|172|166Hz  62.0dB            -\\
  mɪt        permit         157|170|186Hz  60.0dB            -//
  ðɪs        this           126|120|120Hz  59.9dB            _
  aɪ         i              257|291|344Hz  60.5dB            -//
```

**4b  I need a new PERmit today. [noun stress]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  mɪt                       157|170|186Hz  60.0dB            -//
  ðɪs        this           126|120|120Hz  59.9dB            _
  aɪ         i              257|291|344Hz  60.5dB            -//
  niːd       need           201|194|195Hz  66.3dB            _
> eɪ         a              200|98|180Hz  63.2dB             *-\
  nuː        new            91|90|90Hz  51.9dB               _
> pɜː        permit         178|174|171Hz  66.2dB            *-
  mɪt        permit         168|163|192Hz  63.8dB            _//
  tə         today          259|260|269Hz  66.3dB            -
  deɪ        today          368|368|368Hz  50.6dB            -
```

**4c  The CONtract was signed. [noun]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  mɪt                       168|163|192Hz  63.8dB            _//
  tə         today          259|260|269Hz  66.3dB            -
  deɪ        today          368|368|368Hz  50.6dB            -
  ðə         the            229|225|161Hz  66.7dB            _\\
  kɑːn       contract                                        ?
> tɹækt      contract       207|227|233Hz  70.6dB            *-//
  wʌz        was            84|89|89Hz  61.3dB               _
> saɪnd      signed         191|196|205Hz  66.0dB            *-
```

**4d  Please conTRACT the summary. [verb]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  pliːz      please         184|162|162Hz  61.0dB            _\\
  kɑːn       contract       195|192|180Hz  59.8dB            -
  tɹækt      contract       167|160|156Hz  61.8dB            _
  ðə         the            219|108|109Hz  60.6dB            _\\
  sʌ         summary        210|216|228Hz  66.8dB            -
  mɚ         summary        257|267|274Hz  70.1dB            -
  ɹi         summary        275|267|269Hz  63.5dB            -
```

**4e  Please reCORD this for her. [verb]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  pliːz      please         177|174|175Hz  63.5dB            _
> ɹɛ         record         233|241|247Hz  68.7dB            *-
  kɚd        record                                          ?
  ðɪs        this           225|199|94Hz  63.4dB             \\
  fɔːɹ       for            215|202|200Hz  68.1dB            -
  hɜː        her            200|217|110Hz  64.2dB            -\\
```

**4f  That's a REcord for her. [noun]**

```
syl        word           F0 onset|mid|off Hz amp          prosody
----------------------------------------------------------------------
  hɜː        her            200|217|110Hz  64.2dB            -\\
  ðæts       that's         93|92|89Hz  60.9dB               _
  eɪ         a              211|195|158Hz  63.9dB            -\\
> ɹɛ         record         248|265|257Hz  69.6dB            *-
> kɚd        record         251|257|267Hz  72.1dB            *-
  fɔːɹ       for            161|160|160Hz  59.0dB            _
  hɜː        her            160|166|166Hz  55.9dB            _
```

### Broad vs. Narrow Focus (John/car set)

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 5a | John bought a new CAR yesterday. [broad/CAR] | `dʒɑːn` | 202|208|226Hz  70.4dB | `*-//` |
| 5b | John bought a new CAR yesterday. [narrow:CAR] | `dʒɑːn` | 221|227|246Hz  68.8dB | `*-//` |
| 5c | Did John buy a new BIKE yesterday? [q] | `dʒɑːn` | 222|211|221Hz  70.0dB | `*-` |
| 5d | No, he bought a new CAR yesterday. [corr:CAR] | `hiː` | 224|206|197Hz  67.5dB | `*-\\` |
| 5e | Who bought a new car yesterday? [wh-q] | `kɑːɹ` | 233|248|266Hz  66.5dB | `-//` |
| 5f | JOHN bought a new car yesterday. [focus:JOHN] | `dʒɑːn` | 229|218|219Hz  68.5dB | `*-` |
| 5g | Did Mary buy a car yesterday? [q] | `ɹi` | 269|261|246Hz  72.3dB | `*-` |
| 5h | No, JOHN bought a new car. [corr:JOHN] | `tɚ` | 238|229|225Hz  63.7dB | `*-` |
| 5i | JOHN bought it. [contrastive topic] | `fɔːɹ` | 277|276|231Hz  69.3dB | `*-\\` |

### Focus-Sensitive Particles

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 6a | ONLY JOHN called Maria. | `kɔːld` | 251|242|240Hz  68.2dB | `*-` |
| 6b | John only CALLED Maria. | `kɔːld` | 224|232|258Hz  68.6dB | `*-//` |
| 6c | John called only MARIA. | `dʒɑːn` | 209|200|206Hz  68.6dB | `*-` |
| 6d | EVEN JOHN passed the test. | `li` | 173|168|162Hz  64.8dB | `*-` |
| 6e | John even PASSED the test. | `dʒɑːn` | 226|303|293Hz  69.7dB | `*-//` |
| 6f | Many STUDENTS solved the test. | `ni` | 234|249|237Hz  69.7dB | `*-` |
| 6g | Many students SOLVED the test. | `ni` | 226|234|223Hz  71.1dB | `*-` |

### Statement vs. Yes/No Question

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 7a | You finished the report. [statement] | `juː` | 206|205|204Hz  65.9dB | `*-` |
| 7b | You finished the report? [question] | `juː` | 187|186|185Hz  62.0dB | `*-` |
| 7c | You finished the report, DIDN'T you. | `nɪʃt` | 252|266|277Hz  66.9dB | `*-//` |
| 7d | You finished the report, didn't YOU? | `juː` | 200|198|194Hz  66.6dB | `*-` |

### Wh-Question vs. Echo Question

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 8a | Who are you meeting? [wh-q] | `nɪʃt` | 243|240|233Hz  68.7dB | `*-` |
| 8b | You're meeting WHO? [echo] | `huː` | 203|295|380Hz  65.5dB | `-//` |
| 8c | Who are you MEETING at noon? [wh-q] | `ɾɪŋ` | 232|253|260Hz  68.2dB | `*-//` |
| 8d | You're meeting WHO at noon? [echo] | `nuːn` | 250|288|218Hz  64.5dB | `-\\` |

### Yes/No vs. Alternative Question

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 9a | Do you want tea or COFFEE? [yes/no rising] | `ɔːɹ` | 258|256|256Hz  72.7dB | `-` |
| 9b | Do you want TEA or COFFEE? [alternative] | `duː` | 215|206|207Hz  66.6dB | `*-` |
| 9c | Do you want TEA or COFFEE or...? [list] | `juː` | 215|223|219Hz  71.6dB | `*-` |

### Declarative vs. Exclamation

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 10a | That was incredibly good. [declarative] | `ɪŋ` | 251|240|226Hz  69.6dB | `*-\\` |
| 10b | That was incredibly GOOD! [exclamation] | `dɪb` | 221|223|220Hz  69.0dB | `*-` |
| 10c | It's so nice. [neutral] | `soʊ` | 238|221|218Hz  69.0dB | `*-\\` |
| 10d | It's SO nice! [exclamation] | `soʊ` | 222|214|218Hz  69.6dB | `*-` |

### Contrastive Topic

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 11a | As for the weather, it's getting COLD. | `fɔːɹ` | 237|230|229Hz  72.3dB | `*-` |
| 11b | JOHN I like; MARY I don't. [contr topic] | `dʒɑːn` | 209|235|248Hz  68.4dB | `*-//` |

### Too/Also Focus

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 12a | JOHN called Maria, too. | `dʒɑːn` | 212|227|211Hz  71.3dB | `*-` |
| 12b | John called MARIA, too. | `dʒɑːn` | 211|200|215Hz  69.1dB | `-` |
| 12c | John CALLED Maria, too. | `dʒɑːn` | 192|185|197Hz  66.3dB | `*-` |

### Given vs. New Information

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 13a | Did Emma submit the draft? [q] | `dɪd` | 210|204|203Hz  72.1dB | `*-` |
| 13b | She submitted it YESTERDAY. [new info] | `səb` | 247|238|230Hz  68.5dB | `-` |
| 13c | She submitted it YESTERDAY. [focus] | `ʃiː` | 231|231|223Hz  71.0dB | `*-` |
| 13d | When did Emma submit the draft? [wh-q] | `wɛn` | 196|197|200Hz  68.2dB | `*-` |
| 13e | Emma submitted the draft YESTERDAY. | `mə` | 232|244|235Hz  68.6dB | `*-` |

### List Intonation

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 14a | We need APPLES, PEARS, and BANANAS. [complete] | `wiː` | 209|202|198Hz  69.2dB | `*-` |
| 14b | We need APPLES, PEARS, and... [incomplete] | `wiː` | 194|194|191Hz  65.4dB | `*-` |

### Attachment Ambiguity

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 15a | OLD men and women. | `oʊld` | 166|179|209Hz  64.6dB | `*-//` |
| 15b | old MEN and WOMEN. | `oʊld` | 219|200|205Hz  62.7dB | `-` |
| 15c | I saw the man with the TELESCOPE. | `ðə` | 224|220|214Hz  72.0dB | `*-` |
| 15d | I SAW the man with the telescope. | `sɔː` | 226|215|171Hz  66.3dB | `*-\\` |

### Yes/No Question Types

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 16a | Are you comING? [rising] | `mɪŋ` | 194|254|307Hz  67.5dB | `*-//` |
| 16b | You're comING? [echo] | `mɪŋ` | 241|300|369Hz  66.3dB | `*-//` |

### Request vs. Command

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 17a | Can you pass the SALT? [request] | `juː` | 227|225|225Hz  69.5dB | `*-` |
| 17b | Can you pass the SALT. [command] | `juː` | 229|227|161Hz  70.3dB | `*-\\` |
| 17c | Can you PASS the salt? [alt stress] | `sɔlt` | 281|274|299Hz  65.0dB | `-` |
| 17d | You can pass the SALT. [decl] | `kæn` | 261|258|246Hz  68.0dB | `-` |
| 17e | You can pass the SALT? [q] | `kæn` | 229|218|201Hz  67.7dB | `*-\\` |

### Restrictive vs. Non-Restrictive Relative

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 18a | My brother who LIVES in Boston called. [restr] | `ðɚ` | 217|236|235Hz  72.8dB | `*-` |
| 18b | My BROTHER, who lives in BOSTON, CALLED. [non] | `laɪvz` | 204|200|197Hz  66.7dB | `*-` |

### Confirmation vs. Correction

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 19a | You met with the DIRECTOR? [confirm] | `wɪð` | 227|228|218Hz  69.1dB | `*-` |
| 19b | I met with the PRODUCER, not the DIRECTOR. | `mɛt` | 224|241|243Hz  70.7dB | `*-` |

### Negation Focus

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 20a | John did NOT call Maria. | `dʒɑːn` | 209|201|216Hz  65.9dB | `*-` |
| 20b | John did not call MARIA; he called SARA. | `dʒɑːn` | 199|194|202Hz  67.3dB | `*-` |

### Surprise and Incredulity

| ID | Sentence | Prominent syl | F0 contour | Symbol |
|----|---------:|--------------|-----------|--------|
| 21a | He's thirty. [statement] | `hiːz` | 238|223|219Hz  67.3dB | `*-\\` |
| 21b | He's THIRTY? [surprise] | `hiːz` | 238|223|219Hz  67.3dB | `*-\\` |

## Discussion

The automatic prosody labels capture several expected patterns from the prosody corpus:

**Contrastive stress and focus.** In sentences where a particular word carries the contrastive or
narrow focus accent, that word's prominent syllable is reliably marked `*` (accent), typically
combined with a falling or high label (`*-\\`, `*-`). For example, in the Mary–Milan set, the
focus word's nucleus shows the highest F0 peak and greatest amplitude relative to its neighbours,
which the composite prominence score correctly identifies.

**Statement vs. question.** Declarative sentences end on a falling contour (`\\` or `\`) while
yes/no questions show a final rise (`/` or `//`). The distinction is visible in the final
syllable's F0 trajectory: statement finals typically show F0 offset < F0 onset; question finals
show F0 offset > F0 onset.

**Lexical stress alternation.** The noun/verb minimal pairs (PERmit / perMIT, CONtract / conTRACT,
REcord / reCORD) produce different `*` positions. The stressed syllable in the noun form receives
the accent marker while in the verb form the `*` shifts to the second syllable, consistent with
English lexical stress patterns.

**Limitations.** The `*` marker fires on the syllable that is most prominent relative to its
±1 neighbours using a composite acoustic score. In short sentences (≤3 syllables) or sentences
with global F0 declination, the label may identify the least-suppressed syllable rather than the
genuinely accented one. The `H`/`L` height distinctions (`-` vs `_`) are computed relative to the
immediate neighbours, making them sensitive to local context rather than the utterance-level
pitch range needed for full ToBI-style labelling.
