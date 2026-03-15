package ai.autocrab.android.node

import ai.autocrab.android.protocol.AutoCrabCalendarCommand
import ai.autocrab.android.protocol.AutoCrabCanvasA2UICommand
import ai.autocrab.android.protocol.AutoCrabCanvasCommand
import ai.autocrab.android.protocol.AutoCrabCameraCommand
import ai.autocrab.android.protocol.AutoCrabCapability
import ai.autocrab.android.protocol.AutoCrabContactsCommand
import ai.autocrab.android.protocol.AutoCrabDeviceCommand
import ai.autocrab.android.protocol.AutoCrabLocationCommand
import ai.autocrab.android.protocol.AutoCrabMotionCommand
import ai.autocrab.android.protocol.AutoCrabNotificationsCommand
import ai.autocrab.android.protocol.AutoCrabPhotosCommand
import ai.autocrab.android.protocol.AutoCrabScreenCommand
import ai.autocrab.android.protocol.AutoCrabSmsCommand
import ai.autocrab.android.protocol.AutoCrabSystemCommand

data class NodeRuntimeFlags(
  val cameraEnabled: Boolean,
  val locationEnabled: Boolean,
  val smsAvailable: Boolean,
  val voiceWakeEnabled: Boolean,
  val motionActivityAvailable: Boolean,
  val motionPedometerAvailable: Boolean,
  val debugBuild: Boolean,
)

enum class InvokeCommandAvailability {
  Always,
  CameraEnabled,
  LocationEnabled,
  SmsAvailable,
  MotionActivityAvailable,
  MotionPedometerAvailable,
  DebugBuild,
}

enum class NodeCapabilityAvailability {
  Always,
  CameraEnabled,
  LocationEnabled,
  SmsAvailable,
  VoiceWakeEnabled,
  MotionAvailable,
}

data class NodeCapabilitySpec(
  val name: String,
  val availability: NodeCapabilityAvailability = NodeCapabilityAvailability.Always,
)

data class InvokeCommandSpec(
  val name: String,
  val requiresForeground: Boolean = false,
  val availability: InvokeCommandAvailability = InvokeCommandAvailability.Always,
)

object InvokeCommandRegistry {
  val capabilityManifest: List<NodeCapabilitySpec> =
    listOf(
      NodeCapabilitySpec(name = AutoCrabCapability.Canvas.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.Screen.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.Device.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.Notifications.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.System.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.AppUpdate.rawValue),
      NodeCapabilitySpec(
        name = AutoCrabCapability.Camera.rawValue,
        availability = NodeCapabilityAvailability.CameraEnabled,
      ),
      NodeCapabilitySpec(
        name = AutoCrabCapability.Sms.rawValue,
        availability = NodeCapabilityAvailability.SmsAvailable,
      ),
      NodeCapabilitySpec(
        name = AutoCrabCapability.VoiceWake.rawValue,
        availability = NodeCapabilityAvailability.VoiceWakeEnabled,
      ),
      NodeCapabilitySpec(
        name = AutoCrabCapability.Location.rawValue,
        availability = NodeCapabilityAvailability.LocationEnabled,
      ),
      NodeCapabilitySpec(name = AutoCrabCapability.Photos.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.Contacts.rawValue),
      NodeCapabilitySpec(name = AutoCrabCapability.Calendar.rawValue),
      NodeCapabilitySpec(
        name = AutoCrabCapability.Motion.rawValue,
        availability = NodeCapabilityAvailability.MotionAvailable,
      ),
    )

  val all: List<InvokeCommandSpec> =
    listOf(
      InvokeCommandSpec(
        name = AutoCrabCanvasCommand.Present.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasCommand.Hide.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasCommand.Navigate.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasCommand.Eval.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasCommand.Snapshot.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasA2UICommand.Push.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasA2UICommand.PushJSONL.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabCanvasA2UICommand.Reset.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabScreenCommand.Record.rawValue,
        requiresForeground = true,
      ),
      InvokeCommandSpec(
        name = AutoCrabSystemCommand.Notify.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabCameraCommand.List.rawValue,
        requiresForeground = true,
        availability = InvokeCommandAvailability.CameraEnabled,
      ),
      InvokeCommandSpec(
        name = AutoCrabCameraCommand.Snap.rawValue,
        requiresForeground = true,
        availability = InvokeCommandAvailability.CameraEnabled,
      ),
      InvokeCommandSpec(
        name = AutoCrabCameraCommand.Clip.rawValue,
        requiresForeground = true,
        availability = InvokeCommandAvailability.CameraEnabled,
      ),
      InvokeCommandSpec(
        name = AutoCrabLocationCommand.Get.rawValue,
        availability = InvokeCommandAvailability.LocationEnabled,
      ),
      InvokeCommandSpec(
        name = AutoCrabDeviceCommand.Status.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabDeviceCommand.Info.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabDeviceCommand.Permissions.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabDeviceCommand.Health.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabNotificationsCommand.List.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabNotificationsCommand.Actions.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabPhotosCommand.Latest.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabContactsCommand.Search.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabContactsCommand.Add.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabCalendarCommand.Events.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabCalendarCommand.Add.rawValue,
      ),
      InvokeCommandSpec(
        name = AutoCrabMotionCommand.Activity.rawValue,
        availability = InvokeCommandAvailability.MotionActivityAvailable,
      ),
      InvokeCommandSpec(
        name = AutoCrabMotionCommand.Pedometer.rawValue,
        availability = InvokeCommandAvailability.MotionPedometerAvailable,
      ),
      InvokeCommandSpec(
        name = AutoCrabSmsCommand.Send.rawValue,
        availability = InvokeCommandAvailability.SmsAvailable,
      ),
      InvokeCommandSpec(
        name = "debug.logs",
        availability = InvokeCommandAvailability.DebugBuild,
      ),
      InvokeCommandSpec(
        name = "debug.ed25519",
        availability = InvokeCommandAvailability.DebugBuild,
      ),
      InvokeCommandSpec(name = "app.update"),
    )

  private val byNameInternal: Map<String, InvokeCommandSpec> = all.associateBy { it.name }

  fun find(command: String): InvokeCommandSpec? = byNameInternal[command]

  fun advertisedCapabilities(flags: NodeRuntimeFlags): List<String> {
    return capabilityManifest
      .filter { spec ->
        when (spec.availability) {
          NodeCapabilityAvailability.Always -> true
          NodeCapabilityAvailability.CameraEnabled -> flags.cameraEnabled
          NodeCapabilityAvailability.LocationEnabled -> flags.locationEnabled
          NodeCapabilityAvailability.SmsAvailable -> flags.smsAvailable
          NodeCapabilityAvailability.VoiceWakeEnabled -> flags.voiceWakeEnabled
          NodeCapabilityAvailability.MotionAvailable -> flags.motionActivityAvailable || flags.motionPedometerAvailable
        }
      }
      .map { it.name }
  }

  fun advertisedCommands(flags: NodeRuntimeFlags): List<String> {
    return all
      .filter { spec ->
        when (spec.availability) {
          InvokeCommandAvailability.Always -> true
          InvokeCommandAvailability.CameraEnabled -> flags.cameraEnabled
          InvokeCommandAvailability.LocationEnabled -> flags.locationEnabled
          InvokeCommandAvailability.SmsAvailable -> flags.smsAvailable
          InvokeCommandAvailability.MotionActivityAvailable -> flags.motionActivityAvailable
          InvokeCommandAvailability.MotionPedometerAvailable -> flags.motionPedometerAvailable
          InvokeCommandAvailability.DebugBuild -> flags.debugBuild
        }
      }
      .map { it.name }
  }
}
