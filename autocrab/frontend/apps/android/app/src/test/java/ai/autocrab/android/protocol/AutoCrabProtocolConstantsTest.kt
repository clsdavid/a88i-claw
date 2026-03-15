package ai.autocrab.android.protocol

import org.junit.Assert.assertEquals
import org.junit.Test

class AutoCrabProtocolConstantsTest {
  @Test
  fun canvasCommandsUseStableStrings() {
    assertEquals("canvas.present", AutoCrabCanvasCommand.Present.rawValue)
    assertEquals("canvas.hide", AutoCrabCanvasCommand.Hide.rawValue)
    assertEquals("canvas.navigate", AutoCrabCanvasCommand.Navigate.rawValue)
    assertEquals("canvas.eval", AutoCrabCanvasCommand.Eval.rawValue)
    assertEquals("canvas.snapshot", AutoCrabCanvasCommand.Snapshot.rawValue)
  }

  @Test
  fun a2uiCommandsUseStableStrings() {
    assertEquals("canvas.a2ui.push", AutoCrabCanvasA2UICommand.Push.rawValue)
    assertEquals("canvas.a2ui.pushJSONL", AutoCrabCanvasA2UICommand.PushJSONL.rawValue)
    assertEquals("canvas.a2ui.reset", AutoCrabCanvasA2UICommand.Reset.rawValue)
  }

  @Test
  fun capabilitiesUseStableStrings() {
    assertEquals("canvas", AutoCrabCapability.Canvas.rawValue)
    assertEquals("camera", AutoCrabCapability.Camera.rawValue)
    assertEquals("screen", AutoCrabCapability.Screen.rawValue)
    assertEquals("voiceWake", AutoCrabCapability.VoiceWake.rawValue)
    assertEquals("location", AutoCrabCapability.Location.rawValue)
    assertEquals("sms", AutoCrabCapability.Sms.rawValue)
    assertEquals("device", AutoCrabCapability.Device.rawValue)
    assertEquals("notifications", AutoCrabCapability.Notifications.rawValue)
    assertEquals("system", AutoCrabCapability.System.rawValue)
    assertEquals("appUpdate", AutoCrabCapability.AppUpdate.rawValue)
    assertEquals("photos", AutoCrabCapability.Photos.rawValue)
    assertEquals("contacts", AutoCrabCapability.Contacts.rawValue)
    assertEquals("calendar", AutoCrabCapability.Calendar.rawValue)
    assertEquals("motion", AutoCrabCapability.Motion.rawValue)
  }

  @Test
  fun cameraCommandsUseStableStrings() {
    assertEquals("camera.list", AutoCrabCameraCommand.List.rawValue)
    assertEquals("camera.snap", AutoCrabCameraCommand.Snap.rawValue)
    assertEquals("camera.clip", AutoCrabCameraCommand.Clip.rawValue)
  }

  @Test
  fun screenCommandsUseStableStrings() {
    assertEquals("screen.record", AutoCrabScreenCommand.Record.rawValue)
  }

  @Test
  fun notificationsCommandsUseStableStrings() {
    assertEquals("notifications.list", AutoCrabNotificationsCommand.List.rawValue)
    assertEquals("notifications.actions", AutoCrabNotificationsCommand.Actions.rawValue)
  }

  @Test
  fun deviceCommandsUseStableStrings() {
    assertEquals("device.status", AutoCrabDeviceCommand.Status.rawValue)
    assertEquals("device.info", AutoCrabDeviceCommand.Info.rawValue)
    assertEquals("device.permissions", AutoCrabDeviceCommand.Permissions.rawValue)
    assertEquals("device.health", AutoCrabDeviceCommand.Health.rawValue)
  }

  @Test
  fun systemCommandsUseStableStrings() {
    assertEquals("system.notify", AutoCrabSystemCommand.Notify.rawValue)
  }

  @Test
  fun photosCommandsUseStableStrings() {
    assertEquals("photos.latest", AutoCrabPhotosCommand.Latest.rawValue)
  }

  @Test
  fun contactsCommandsUseStableStrings() {
    assertEquals("contacts.search", AutoCrabContactsCommand.Search.rawValue)
    assertEquals("contacts.add", AutoCrabContactsCommand.Add.rawValue)
  }

  @Test
  fun calendarCommandsUseStableStrings() {
    assertEquals("calendar.events", AutoCrabCalendarCommand.Events.rawValue)
    assertEquals("calendar.add", AutoCrabCalendarCommand.Add.rawValue)
  }

  @Test
  fun motionCommandsUseStableStrings() {
    assertEquals("motion.activity", AutoCrabMotionCommand.Activity.rawValue)
    assertEquals("motion.pedometer", AutoCrabMotionCommand.Pedometer.rawValue)
  }
}
