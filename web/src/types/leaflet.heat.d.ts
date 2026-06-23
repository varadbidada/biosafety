/* eslint-disable @typescript-eslint/no-explicit-any */
import * as L from "leaflet";

declare module "leaflet" {
  export function heatLayer(
    latlngs: Array<[number, number, number]>,
    options?: Record<string, any>,
  ): L.Layer;
}
