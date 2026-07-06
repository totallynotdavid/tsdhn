#set document(
  title: [%%title%%],
  author: "%%author%%",
)
#set page(
  paper: "a4",
  margin: 1.65cm,
  columns: 2,
)
#set text(
  font: "Libertinus Serif",
  size: 11pt,
  lang: "es",
)
#set par(justify: true, first-line-indent: 0pt)
#set table.hline(stroke: 0.6pt)
#show heading: set text(font: "Liberation Sans", size: 13pt)
#show figure.caption: set text(size: 9pt)

#align(center)[
  #text(font: "Liberation Sans", weight: "bold", size: 16pt)[%%title%%] \
  #text(font: "Liberation Sans")[%%author%%] \
  #text(font: "Liberation Sans")[%%date%%]
]

= Introducción

Este reporte preliminar de tsunami de origen lejano ha sido elaborado en forma automática por el modelo numérico TSDHN-2022. Las dimensiones de la fuente sísmica se calculan a partir de las ecuaciones de Papazachos et al. (2004). El mecanismo focal del terremoto se toma de la base de datos del Global CMT. El campo de deformación se obtiene a partir de las ecuaciones analíticas de Okada (1992).

La simulación de la propagación del tsunami se realiza con el modelo numérico TUNAMI, modelo lineal y en coordenadas esféricas (Imamura et al., 2006). La grilla batimétrica computacional abarca el Océano Pacífico, con una resolución de 4 min o 240 s. El cálculo de las isócronas de tiempos de arribo para el Océano Pacífico se realizó con el modelo Tsunami Travel Time (Wessel, 2009).

Se han colocado 3 mareógrafos virtuales en los puertos de Talara, Callao y Matarani. Se utilizó la ley de Green para la corrección de la amplitud de los mareogramas, debido a que los nodos computacionales no coinciden necesariamente con la ubicación de las estaciones mareográficas costeras (Satake, 2015).

El tiempo promedio de cómputo para una PC i7 es de 15 min para una ventana de tiempo de simulación de 28 horas (Figura 1). Sin embargo, el supercomputador DHN demora menos de 2 minutos.

*Nota:* El resultado del modelo TSDHN-2022 es una estimación referencial y debe ser utilizado para obtener los parámetros de tsunamis de origen lejano, es decir fuera de las fronteras del litoral de Perú. Para eventos de origen cercano, se debe utilizar el modelo Pre-Tsunami (Jimenez et al., 2018).

#pagebreak()

= Análisis

El cuadro 1 muestra los parámetros hipocentrales y mecanismo focal del terremoto.

#align(center)[
  #table(
    columns: (auto, auto),
    stroke: none,
    align: (left, center),
    table.hline(),
    [*Parámetro*], [*Valor*],
    table.hline(),
    [Latitud], [%%lat%%°],
    [Longitud], [%%lon%%°],
    [], [],
    [Profundidad], [%%depth%% km],
    [Magnitud], [%%magnitude%% $M_w$],
    [], [],
    [Strike], [%%strike%%°],
    [Dip], [%%dip%%°],
    [Rake], [%%rake%%°],
    table.hline(),
  )
]

La figura 1 muestra el mapa de propagación de la máxima energía, la ubicación del epicentro está representado por la esfera focal y las estaciones mareográficas están representadas por los triángulos azules.

#figure(
  image("maxola.svg", width: 95%),
  caption: [Mapa de máxima altura de propagación del tsunami. La esfera focal representa el epicentro. Los triángulos azules representan a las estaciones mareográficas.],
)

La figura 2 muestra las isócronas de los tiempos de arribo del tsunami para todo el Océano Pacífico. La esfera focal representa el epicentro.

#figure(
  image("ttt.svg", width: 100%),
  caption: [Mapa de tiempo de arribo del tsunami],
)

La figura 3 muestra los mareogramas simulados para las estaciones del litoral del Perú, de norte a sur: Talara, Callao y Matarani.

#figure(
  image("mareograma.svg", width: 100%),
  caption: [Mareogramas simulados en las estaciones de Talara, Callao y Matarani.],
)

El cuadro 2 muestra los valores de los tiempos de arribo (hh:mm) y la máxima altura del tsunami en las estaciones mareográficas del litoral peruano.

#align(center)[
  #table(
    columns: (auto, auto, auto),
    stroke: none,
    align: (left, center, center),
    table.hline(),
    [*Estación*], [*Tiempo de arribo*], [*Máximo (m)*],
    table.hline(),
    [%%station1_name%%], [%%station1_time%%], [%%station1_max%%],
    [%%station2_name%%], [%%station2_time%%], [%%station2_max%%],
    [%%station3_name%%], [%%station3_time%%], [%%station3_max%%],
    table.hline(),
  )
]

= Bibliografía

[1] B. Papazachos, E. Scordilis, C. Panagiotopoulus and G. Karakaisis. Global relations between seismic fault parameters and moment magnitude of earthquakes. Bulletin of Geological Society of Greece, vol XXXVI, pp 1482-1489 (2004).

[2] Y. Okada. Internal deformation in a half space. Bull. Seismol. Soc. Am. 82(2) 1018-1040 (1992).

[3] F. Imamura, A. Yalciner and G. Ozyurt. Tsunami Modelling Manual (TUNAMI model). Tohoku University, Sendai. (2006).

[4] P. Wessel. Analysis of observed and predicted tsunami travel times for the Pacific and Indian Oceans. Pure Appl. Geophys., vol 166, pp 301--324 (2009).

[5] K. Satake. Tsunamis, inverse problem of. Encyclopedia of Complexity and Systems Science, pp 1--20 (2015).

[6] C. Jimenez, C. Carbonel and J. Rojas. Numerical procedure to forecast the tsunami parameters from a database of pre-simulated seismic unit sources. Pure Appl. Geophys., vol 175, pp 1473--1483 (2018).
