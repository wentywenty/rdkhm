export class PinRecord {
  physical_pin: number;
  gpio: number;
  controller: string;
  line: number;
  usable_as_gpio: boolean;
  mux_owner: string;
  soc_name: string;
  note: string;

  constructor(pin: number, gpio: number, controller: string, line: number, usable: boolean, owner: string, soc: string, note: string) {
    this.physical_pin = pin;
    this.gpio = gpio;
    this.controller = controller;
    this.line = line;
    this.usable_as_gpio = usable;
    this.mux_owner = owner;
    this.soc_name = soc;
    this.note = note;
  }
}

export const PIN_DATA: PinRecord[] = [
  new PinRecord(3, 390, "ls_gpio0", 11, false, "341c0000.i2c", "I2C5_SDA", "muxed to i2c5; disable it in DTB to use this pin as GPIO"),
  new PinRecord(5, 389, "ls_gpio0", 10, false, "341c0000.i2c", "I2C5_SCL", "muxed to i2c5; disable it in DTB to use this pin as GPIO"),
  new PinRecord(7, 420, "dsp_gpio", 9, true, "", "I2S1_MCLK", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(8, 383, "ls_gpio0", 4, false, "34070000.serial", "UART1_TXD", "muxed to uart1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(10, 384, "ls_gpio0", 5, false, "34070000.serial", "UART1_RXD", "muxed to uart1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(11, 380, "ls_gpio0", 1, true, "", "UART7_TXD", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(12, 421, "dsp_gpio", 10, true, "", "I2S1_BCLK", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(13, 379, "ls_gpio0", 0, true, "", "UART7_RXD", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(15, 388, "ls_gpio0", 9, true, "", "UART2_TXD", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(16, 382, "ls_gpio0", 3, true, "", "UART6_TXD", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(18, 402, "ls_gpio0", 23, true, "", "SPI2_MOSI", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(19, 398, "ls_gpio0", 19, false, "34010000.spi", "SPI1_MOSI", "muxed to spi1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(21, 397, "ls_gpio0", 18, false, "34010000.spi", "SPI1_MISO", "muxed to spi1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(22, 387, "ls_gpio0", 8, true, "", "UART2_RXD", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(23, 395, "ls_gpio0", 16, false, "34010000.spi", "SPI1_SCLK", "muxed to spi1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(24, 394, "ls_gpio0", 15, false, "34010000.spi", "SPI1_CSN1", "muxed to spi1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(26, 396, "ls_gpio0", 17, false, "34010000.spi", "SPI1_CSN0", "muxed to spi1; disable it in DTB to use this pin as GPIO"),
  new PinRecord(27, 355, "ls_gpio1", 8, false, "340b0000.i2c", "I2C0_SDA", "muxed to i2c0; disable it in DTB to use this pin as GPIO"),
  new PinRecord(28, 354, "ls_gpio1", 7, false, "340b0000.i2c", "I2C0_SCL", "muxed to i2c0; disable it in DTB to use this pin as GPIO"),
  new PinRecord(29, 399, "ls_gpio0", 20, true, "", "SPI2_SCLK", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(31, 400, "ls_gpio0", 21, true, "", "I2C1_SDA", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(32, 356, "ls_gpio1", 9, false, "34170000.pwm", "PWM6", "muxed to pwm3; disable it in DTB to use this pin as GPIO"),
  new PinRecord(33, 357, "ls_gpio1", 10, false, "34170000.pwm", "PWM7", "muxed to pwm3; disable it in DTB to use this pin as GPIO"),
  new PinRecord(35, 422, "dsp_gpio", 11, true, "", "I2S1_LRCK", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(36, 381, "ls_gpio0", 2, true, "", "BIFSD_CLK", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(37, 401, "ls_gpio0", 22, true, "", "SPI2_MISO", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(38, 423, "dsp_gpio", 12, true, "", "I2S1_SDIN", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
  new PinRecord(40, 424, "dsp_gpio", 13, true, "", "I2S1_SDOUT", "no driver claims the pin; RDK hobot-gpio assumes the default mux is GPIO"),
];
