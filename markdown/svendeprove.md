---
__Advertisement :)__

- __[pica](https://nodeca.github.io/pica/demo/)__ - high quality and fast image
  resize in browser.
- __[babelfish](https://github.com/nodeca/babelfish/)__ - developer friendly
  i18n with plurals support and easy syntax.

You will like those projects!

å

---

# Artek DTU - <sub><sup>[find.artek.byg.dtu.dk](http://find.artek.byg.dtu.dk/)</sup></sub>

## Artek Student Rapport Applikation

<br/>

### Indholdfortegnelse
1. [Introduktion](#introduktion)
2. [Problemstilling](#problemstilling)
   1. Udfordringer
      1. Migration af Data
      2. Udgåede libraries









### Introduktion <a name="introduktion"></a>
Siden 1996 har studerende fra Danmark's Tekniske Universitet (DTU) udført fæltarbejde på Grønland og skrevet tekniske rapporter med fokus på samfundet, teknologier og miløet. I år 2000 blev "Center of Artic Technology (ARTEK) etableret. Formålet med ARTEK er at samle alt som DTU har med det arktiske område at gøre under en ledelse. Grundet mange års fæltarbejde er der blevet lavet en masse rapporter. Indtil da har rapporter været lagret og tilgængelige på en FTP server. På denne server kan man finde rapporter ved at søge på året rapporten udkom på. Søgningen var derfor ikke særlig effiktiv. Det er et ønske fra de Grønlandske myndigheder at forbedre søgemulighederne på gamle rapporter. Hvis det er nemmere at finde relavante repporter, geografiske data, kan resultaterne bruges til at fremtidige studier og være grundlag for politiske beslutninger. På grund af interessen for at gamle rapporter skal være lættere tilgængelige, er en ny database blevet etableret. Det er gjort af Thomas Ingeman-Nielsen lektor for ARTEK. Denne database er blevet lavet for at gøre det nemmere at finde relevante rappporter blandt alle alle dem som skrevet af DTU studerende og/eller tilhørende ARTEK. Rapportene er opdelt i kategorier, og det er muligt at søge på nøgleord, emner, rapportitlen, resumeet eller geografisk lokation.


### Formål med find.artek
Formålet er at gøre det nemmere at finde ARTEKS rapporter. På nuværende tidspunkt er det muligt at finde rapport på ved hjælp af katergorier visualiseret i et grafisk web interface, eller man kan søge rapporter med nøgleord, titel, resume eller geografisk lokation. En udvidelse ville være at kunne søge på sætninger som indtræffer inde i selve rapporten.


### Problemstilling <a name="problemstilling"></a>
Den overordnede problemstilling er at find.artek er nu implementeret i en forædlet version af Django, hvilket DTU's sikkerhedspolitik ikke er kompatibelt med. Altså skal find.arktek migreres over til- eller re-implemteres i den nyeste version af Django. 
find.artek blev implementeret i den første version af Django frameworket - version 1. P Applikation blev implementeret i en 


#### Udfordringer
find.artek er implementeret på et tidspunkt hvor Django frameworket ikke var helt modent. Det var ikke beta, men da version 1.7 kom ud havde den integreret et trejde parts biblotek til sig som hedder south. Dette biblotek bruges til at synkronisere nogle modeller defineret i Django, som automatisk bliver genereret i en SQL database. 
* Problem 1: Databasen som bruges er en sqllite3 hvilket gør det svært at modificere data og struktur i selve databasen.
* Problem 2: South og den integrede udgave af South er ikke enige om hvordan en model skal udforme sig i databasen.
* Problem 3: Hvordan migreres alt data'en over i en moderne Django model.
* Løsning til problem 1: 

Mulig


Problemstilling<br>
Applikationen's framework (Django) er forældet og kan derfor ikke være tilgængelig fra DTU's domæne. 

[I august 2022 blev DTU udsat for et hackerangreb.](https://www.dr.dk/nyheder/seneste/dtu-udsat-alvorligt-hackerangreb-alle-skal-skifte-kodeord). Det har kostet DTU og dets medarbejder meget tid og (penge). Det skal så vidt muligt undgås at det sker igen. Efter nye politikker er en Der er blevet fortaget en  åtet mange penge Herefter blev der ryddet gevaldigt op  den august 2022 er blevet hacket, og derfor er der fortaget en større rengøring af servere som ikke længere er med nyeste versioner. Kernen af problemet er at applikation ikke længere supporteres og derfor ikke forsvarligt kan leve pa DTU's servere. Derfor skal applikationen reimplementeres i den nyeste version af Django, for at kunne komme online igen. Der følger en masse pukler (udfordringer) med at fører data over. Samt er mange af de third party libraries døde. stilliJeg arbejder p find_artek.byg.dtu




### h3 Heading
#### h4 Heading
##### h5 Heading
###### h6 Heading


## Horizontal Rules

___

---

***


## Typographic replacements

Enable typographer option to see result.

(c) (C) (r) (R) (tm) (TM) (p) (P) +-

test.. test... test..... test?..... test!....

!!!!!! ???? ,,  -- ---

"Smartypants, double quotes" and 'single quotes'


## Emphasis

**This is bold text**

__This is bold text__

*This is italic text*

_This is italic text_

~~Strikethrough~~


## Blockquotes


> Blockquotes can also be nested...
>> ...by using additional greater-than signs right next to each other...
> > > ...or with spaces between arrows.


## Lists

Unordered

+ Create a list by starting a line with `+`, `-`, or `*`
+ Sub-lists are made by indenting 2 spaces:
  - Marker character change forces new list start:
    * Ac tristique libero volutpat at
    + Facilisis in pretium nisl aliquet
    - Nulla volutpat aliquam velit
+ Very easy!

Ordered

1. Lorem ipsum dolor sit amet
2. Consectetur adipiscing elit
3. Integer molestie lorem at massa


1. You can use sequential numbers...
1. ...or keep all the numbers as `1.`

Start numbering with offset:

57. foo
1. bar


## Code

Inline `code`

Indented code

    // Some comments
    line 1 of code
    line 2 of code
    line 3 of code


Block code "fences"

```
Sample text here...
```

Syntax highlighting

``` js
var foo = function (bar) {
  return bar++;
};

console.log(foo(5));
```

## Tables

| Option | Description                                                               |
| ------ | ------------------------------------------------------------------------- |
| data   | path to data files to supply the data that will be passed into templates. |
| engine | engine to be used for processing templates. Handlebars is the default.    |
| ext    | extension to be used for dest files.                                      |

Right aligned columns

| Option |                                                               Description |
| -----: | ------------------------------------------------------------------------: |
|   data | path to data files to supply the data that will be passed into templates. |
| engine |    engine to be used for processing templates. Handlebars is the default. |
|    ext |                                      extension to be used for dest files. |


## Links

[link text](http://dev.nodeca.com)

[link with title](http://nodeca.github.io/pica/demo/ "title text!")

Autoconverted link https://github.com/nodeca/pica (enable linkify to see)


## Images

![Minion](https://octodex.github.com/images/minion.png)
![Stormtroopocat](https://octodex.github.com/images/stormtroopocat.jpg "The Stormtroopocat")

Like links, Images also have a footnote style syntax

![Alt text][id]

With a reference later in the document defining the URL location:

[id]: https://octodex.github.com/images/dojocat.jpg  "The Dojocat"


## Plugins

The killer feature of `markdown-it` is very effective support of
[syntax plugins](https://www.npmjs.org/browse/keyword/markdown-it-plugin).


### [Emojies](https://github.com/markdown-it/markdown-it-emoji)

> Classic markup: :wink: :crush: :cry: :tear: :laughing: :yum:
>
> Shortcuts (emoticons): :-) :-( 8-) ;)

see [how to change output](https://github.com/markdown-it/markdown-it-emoji#change-output) with twemoji.


### [Subscript](https://github.com/markdown-it/markdown-it-sub) / [Superscript](https://github.com/markdown-it/markdown-it-sup)

- 19^th^
- H~2~O


### [\<ins>](https://github.com/markdown-it/markdown-it-ins)

++Inserted text++


### [\<mark>](https://github.com/markdown-it/markdown-it-mark)

==Marked text==


### [Footnotes](https://github.com/markdown-it/markdown-it-footnote)

Footnote 1 link[^first].

Footnote 2 link[^second].

Inline footnote^[Text of inline footnote] definition.

Duplicated footnote reference[^second].

[^first]: Footnote **can have markup**

    and multiple paragraphs.

[^second]: Footnote text.


### [Definition lists](https://github.com/markdown-it/markdown-it-deflist)

Term 1

:   Definition 1
with lazy continuation.

Term 2 with *inline markup*

:   Definition 2

        { some code, part of Definition 2 }

    Third paragraph of definition 2.

_Compact style:_

Term 1
  ~ Definition 1

Term 2
  ~ Definition 2a
  ~ Definition 2b


### [Abbreviations](https://github.com/markdown-it/markdown-it-abbr)

This is HTML abbreviation example.

It converts "HTML", but keep intact partial entries like "xxxHTMLyyy" and so on.

*[HTML]: Hyper Text Markup Language

### [Custom containers](https://github.com/markdown-it/markdown-it-container)

::: warning
*here be dragons*
:::
